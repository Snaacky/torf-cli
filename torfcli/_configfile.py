# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details
# http://www.gnu.org/licenses/gpl-3.0.txt

import re


class ConfigError(Exception):
    def __init__(self, name, value=None, msg=None):
        if value:
            if not msg:
                msg = 'Invalid value'
            super().__init__(f'{name} = {value}: {msg}')
        else:
            if not msg:
                msg = 'Invalid argument'
            super().__init__(f'{name!r}: {msg}')


_re_bool = re.compile(r'^(\S+)$')
_re_assign = re.compile(r'^(\S+)\s*=\s*(.*)\s*$')

def read(filepath):
    # Read INI-style file into dictionary
    cfg = subcfg = {}
    with open(filepath, 'r') as f:
        for line in (l.strip() for l in f.readlines()):
            # Skip empty lines and comments
            if not line or line[0] == '#':
                continue

            # Start new profile
            if line[0] == '[' and line[-1] == ']':
                profile_name = line[1:-1]
                cfg[profile_name] = subcfg = {}
                continue

            # Boolean option
            bool_match = _re_bool.match(line)
            if bool_match:
                name = bool_match.group(1)
                subcfg[name] = True
                continue

            # Argument that takes a value
            assign_match = _re_assign.match(line)
            if assign_match:
                name = assign_match.group(1)
                value = assign_match.group(2).strip()
                if value[0] == value[-1] == '"' or value[0] == value[-1] == "'":
                    value = value[1:-1]

                # Multiple occurences of the same name turn its value into a list
                if name in subcfg:
                    if not isinstance(subcfg[name], list):
                        subcfg[name] = [subcfg[name]]
                    subcfg[name].append(value)
                else:
                    subcfg[name] = value

                continue

    return cfg


def validate(cfgfile, defaults):
    # Return validated values from cfgfile
    result = {}
    for name,value_cfgfile in tuple(cfgfile.items()):
        # Dictionaries are profiles and will raise errors
        # when they're evaluated below
        if isinstance(value_cfgfile, dict):
            result[name] = validate(value_cfgfile, defaults)
            continue

        # Non-profile names must be present in defaults
        if name not in defaults:
            raise ConfigError(name)

        # Do type checking or coercion
        value_default = defaults[name]
        if type(value_cfgfile) != type(value_default):
            if type(value_default) is list:
                # We expect a list but value is not - there is only one
                # assignment to an argument that can be given multiple times.
                result[name] = [value_cfgfile]
                continue
            elif type(value_cfgfile) is list:
                # We expect a non-list but value is a list - there are multiple
                # assignments for an argument that can be given only once.
                raise ConfigError(name, value=', '.join((repr(item) for item in value_cfgfile)),
                                  msg='Multiple values not allowed')
            elif type(value_default) is bool:
                raise ConfigError(name, value_cfgfile, msg='Assignment to option')
            else:
                raise ConfigError(name, value_cfgfile)

        result[name] = value_cfgfile

    return result


def combine(cli, cfgfile, defaults):
    # Return combined values from CLI args, cfgfile and defaults
    result = {}
    for name in defaults:
        if name in cli:
            result[name] = cli[name]
        elif name in cfgfile:
            result[name] = cfgfile[name]
        else:
            result[name] = defaults[name]

    # Update result with values from specified profile
    profile_names = cli.get('profile', ())
    for profile_name in profile_names:
        try:
            profile = cfgfile[profile_name]
        except KeyError:
            raise ConfigError(profile_name, msg='No such profile')

        for name,value in profile.items():
            if name in cli and cli[name] != defaults[name]:
                continue
            else:
                result[name] = value

    return result