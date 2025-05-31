# this is the PYTHONSTARTUP file for the "gry python" cli command
# see pygrister.cli:open_python for context
from sysconfig import get_python_version, get_platform
from pygrister import __version__
from pygrister.api import GristApi
from pygrister.cli import _CliConfigurator, cli_in_converters, cli_out_converters # type: ignore
gry = GristApi(custom_configurator=_CliConfigurator())
gry.in_converter = cli_in_converters
gry.out_converter = cli_out_converters
print(f'This is Python {get_python_version()} on {get_platform()}, and Pygrister {__version__}.')
print('Here, "gry" is a ready-to-use, pre-configured GristApi instance.')
del get_python_version
del get_platform
del _CliConfigurator
del cli_in_converters
del cli_out_converters
del __version__
