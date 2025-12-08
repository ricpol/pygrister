# this is the PYTHONSTARTUP file for the "gry python" cli command
# see pygrister.cli:open_python for context
from sysconfig import get_python_version, get_platform
from pathlib import Path
from json import loads
from pygrister import __version__
from pygrister.api import GristApi
from pygrister.cli import (
    _CliConfigurator, _CliApiCaller, req_options, 
    cli_in_converters, cli_out_converters) # type: ignore
c = _CliConfigurator()
req_options = {'timeout': int(c.config['GRIST_GRY_TIMEOUT'])}
pth = Path('gryrequest.json') # optional, to pass even more options to Requests
if pth.is_file(): 
    with open(pth, 'r', encoding='utf8') as f:
        req_options.update(loads(f.read()))
a = _CliApiCaller(configurator=c, request_options=req_options)
gry = GristApi(custom_apicaller=a)
gry.in_converter = cli_in_converters
gry.out_converter = cli_out_converters
print(f'This is Python {get_python_version()} on {get_platform()}, and Pygrister {__version__}.')
print('Here, "gry" is a ready-to-use, pre-configured GristApi instance.')
del get_python_version
del get_platform
del Path
del loads
del GristApi
del _CliConfigurator
del _CliApiCaller
del cli_in_converters
del cli_out_converters
del req_options
del a
del c
del f
del pth
del __version__
