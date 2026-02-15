"""
Gry: the GRist pYthon command line, powered by Pygrister.
=========================================================

Gry is a command line tool for interacting with the Grist API. 
Gry is based on the Pygrister library and maps almost all the Grist APIs, 
even if offering sometimes a simplified, easier to type syntax. 

Gry shares the Pygrister configuration system, meaning that, if you already 
have working Pygrister config files/env variables in place, then Gry will 
also work. In addition, you may put a ``gryconf.json`` file in the current 
directory, and Gry (but not Pygrister) will look there too. Read the 
documentation for more info about the Gry/Pygrister configuration system. 

Gry is organized in "commands", *nouns* referring to the various sections 
of the Grist API: ``gry doc``, ``gry table``, ``gry team`` and so on.
Each command has "sub-commands", actions to perform (mostly *verbs*). 
Sub-commands tend to repeat across commands: ``gry doc new`` adds 
a document, ``gry table new`` adds a table, ``gry col new`` adds a column...

Type ``% gry --help`` to get a list of available commands. Then type, 
for instance, ``% gry doc --help`` to list the sub-commands available 
for ``gry doc``. Finally, something like ``% gry doc new --help`` will show 
how to use a particular sub-command.

Default output is human-readable; pass ``-v`` to get the original Pygrister 
output instead; pass ``-vv`` to get the underlying Grist response (as parsable 
json). Add ``-i`` to also get a dump of request metadata, for inspection. 
Pass ``-q`` to suppress all output. 

Use ``% gry python`` to open a special Python shell, pre-loaded with a 
working Pygrister instance: this way, you can alternate between Gry and 
Pygrister in the same session when needed. 

Example usage::

    % gry team see # get info on the "default" team as per config
    % gry doc see  # the "default" document as per config
    % gry doc see -d f4Y8Tov7TRkTQfUuj7TVdh # select a specific document
    # the best way to switch to another document, from now on: 
    % export GRIST_DOC_ID=f4Y8Tov7TRkTQfUuj7TVdh # or "set" in windows
    % gry doc see # the same as above, but no need to add the "-d" option
    % gry doc see -d bogus_doc # now this will fail...
    % gry doc see -d bogus_doc -i # ...so let's see the request details 
    % gry ws see -w 42 # workspace info, in a nicely formatted table
    % gry ws see -w 42 -vv # the same, in the original raw json
    % gry table new --help # how do I add a table?
    % gry table new name:Text:Name age:Int:Age --table People # like this!
    % gry col list -b People # the columns of our new table
    % gry rec new name:"John Doe" age:42 -b People # populate the table
    % gry sql "select * from People where age>?" -p 35 # run an sql query
    % gry python # let's open a Python shell now!
    >>> gry.list_cols(table_id='People') # "gry" is now a python object
    >>> exit() # and we are back to the shell

`Full documentation <https://pygrister.readthedocs.io>`_ 
`Grist API reference documentation <https://support.getgrist.com/api/>`_
"""

import os
import sys
import subprocess
import json as modjson
from pathlib import Path
from enum import Enum
from typing import Any, List, Optional
from typing_extensions import Annotated

import typer
from rich.console import Console
from rich.table import Table
from requests import RequestException, ConnectionError, Timeout

from pygrister import __version__
from pygrister.api import GristApi
from pygrister.apicaller import ApiCaller
from pygrister.config import Configurator, apikey2output, PYGRISTER_CONFIG

# are we running from a Pyinstaller bundle?
standalone = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

if standalone: # add convenient locations for converters module
    sys.path.append(str(Path(__file__).parent.parent.absolute()))
    sys.path.insert(0, '.')
try:
    from cliconverters import cli_out_converters # type: ignore
except (ModuleNotFoundError, ImportError):
    cli_out_converters = dict()
try:
    from cliconverters import cli_in_converters # type: ignore
except (ModuleNotFoundError, ImportError):
    cli_in_converters = dict()

# we borrow from Cloudflare non-standard 5xx codes 
# to express connection errors (other than HttpError) in Gry
CONN_ERROR = 523 # Requests ConnectionError -> Cf "Origin Is Unreachable"
CONN_TIMEOUT = 522 # Requests Timeout -> Cf "Connection Timed Out"
CONN_MISC_ERROR = 520 # other Requests Exceptions -> Cf "Web Server Returned an Unknown Error"

class _CliApiCaller(ApiCaller):
    """A custom api caller intended for the Pygrister cli."""
    def apicall(self, *args, **kwargs):
        # we try to catch possible connection errors, 
        # so that Gry won't die in flames in front of the user
        try:
            st, res = super().apicall(*args, **kwargs)
        except Timeout as e:
            st = CONN_TIMEOUT
            res = str(e)
        except ConnectionError as e:
            st = CONN_ERROR
            res = str(e)
        except RequestException as e:
            st = CONN_MISC_ERROR
            res = str(e)
        return st, res

class _CliConfigurator(Configurator):
    """A custom configurator intended for the Pygrister cli. 
    
    After loading the configuration from the usual place, 
    this will search for a (optional) "gryconf.json" file   
    located in the current directory, *before* looking for env vars. 
    Note: this configurator also overrides the ``GRIST_RAISE_ERROR``  
    and ``GRIST_SAFEMODE`` config keys, setting both to ``N``.
    """
    @staticmethod
    def get_config() -> dict[str, str]:
        config = dict(PYGRISTER_CONFIG)
        # default value for an additional config key
        config.update({'GRIST_GRY_TIMEOUT': '60'})
        if not standalone:
            pth = Path('~/.gristapi/config.json').expanduser()
            if pth.is_file():
                with open(pth, 'r', encoding='utf8') as f:
                    config.update(modjson.loads(f.read()))
            pth = Path('gryconf.json')
            if pth.is_file(): 
                with open(pth, 'r', encoding='utf8') as f:
                    config.update(modjson.loads(f.read()))
            for k in config.keys():
                try:
                    config[k] = os.environ[k]
                except KeyError:
                    pass
        else: # Pyinstaller bundle: config is stored along "gry.exe" file
            pth = Path(__file__).parent.parent.absolute() / 'gryconf.json'
            if pth.is_file():
                with open(pth, 'r', encoding='utf8') as f:
                    config.update(modjson.loads(f.read()))
        # overrides
        config['GRIST_RAISE_ERROR'] = 'N'
        config['GRIST_SAFEMODE'] = 'N'
        return config

# the global GristApi (re-creadted at every cli call): inside a cli function, 
# all api calls (usually just one but may be more) will use this instance
_c = _CliConfigurator()
req_options = {'timeout': int(_c.config['GRIST_GRY_TIMEOUT'])}
# optional, to pass even more options to Requests
if not standalone:
    pth = Path('gryrequest.json')
else: # Pyinstaller bundle: config is stored along "gry.exe" file
    pth = Path(__file__).parent.parent.absolute() / 'gryrequest.json'
if pth.is_file(): 
    with open(pth, 'r', encoding='utf8') as f:
        req_options.update(modjson.loads(f.read()))
_a = _CliApiCaller(configurator=_c, request_options=req_options)
grist_api = GristApi(custom_apicaller=_a)
grist_api.in_converter = cli_in_converters
grist_api.out_converter = cli_out_converters

# the global Rich console where everything should be printed
cli_console = Console()

BADCALL = 3 # the exit code we reserve for bad call errors (eg http 404)
DONEMSG = '[green]Done.[/green]'
ERRMSG = '[bold red]Error![/bold red]'

# a few helper functions
# ----------------------------------------------------------------------

def _exit_early(st: int, res: Any, quiet: bool, 
                verbose: int, inspect: bool) -> bool:
    # prints output in any possibile case, except the fancy formatted one  
    # that we need when verbose==0 and everything else is fine.
    # return True if we are done and no further output is required, 
    # return False if fancy output is needed
    if inspect and not quiet:
        cli_console.print(grist_api.inspect())
        cli_console.rule()
    if not grist_api.ok:
        if not quiet:
            if verbose < 2:
                cli_console.print(ERRMSG, 'Status:', st, res)
            else:
                cli_console.print(grist_api.apicaller.response_as_json())
        raise typer.Exit(BADCALL)
    if quiet:
        return True
    if verbose == 1:
        cli_console.print(res)
        return True
    if verbose == 2:
        cli_console.print(grist_api.apicaller.response_as_json())
        return True
    return False # meaning that we still have fancy output to produce

def _exit_early_or_print_done(st: int, res: Any, quiet: bool, 
                              verbose: int, inspect: bool) -> None:
    # a shortcut for when the fancy output is just a "Done" message
    if not _exit_early(st, res, quiet, verbose, inspect):
        cli_console.print(DONEMSG)
    
def _exit_early_or_print_id(st: int, res: Any, quiet: bool, 
                            verbose: int, inspect: bool) -> None:
    # a shortcut for when the response is, in fact, an ID
    if not _exit_early(st, res, quiet, verbose, inspect):
        cli_console.print(f'{DONEMSG} Id: {res}')

def _exit_early_or_print_content(st: int, res: Any, quiet: bool, 
                                 verbose: int, inspect: bool) -> None:
    # a shortcut for when the fancy content is, in fact, just the response
    if not _exit_early(st, res, quiet, verbose, inspect):
        cli_console.print(res)

def _make_user_table(response: list[dict]) -> Table:
    table = Table('id', 'name', 'email', 'access')
    for usr in response:
        table.add_row(str(usr['id']), usr['name'], usr['email'], 
                      str(usr['access']))
    return table

def _make_scim_user_data(user: dict, table: Table) -> Table:
    table.add_row('id', str(user['id']))
    table.add_row('name', user['userName'])
    table.add_row('display name', user['displayName'])
    emails = []
    for email in user['emails']:
        e = email['value']
        if email['primary']:
            e += ' (primary)'
        emails.append(e)
    table.add_row('email', '\n'.join(emails))
    table.add_section()
    return table

def _make_sacc_data(sacc: dict, table: Table) -> Table:
    table.add_row('id', str(sacc['id']))
    table.add_row('login', sacc['login'])
    table.add_row('label', sacc['label'])
    table.add_row('description', sacc['description'])
    table.add_row('expires', sacc['expiresAt'])
    table.add_row('valid key', str(sacc['hasValidKey']))
    table.add_section()
    return table

def _user_access_validate(value: str|None):
    legal = 'owners editors viewers members none'
    if value not in legal.split():
        raise typer.BadParameter(f'Access must be one of: {legal}')
    if value == 'none':
        value = None
    return value

def _user_max_access_validate(value: str|None):
    legal = 'owners editors viewers'
    if value not in legal.split():
        raise typer.BadParameter(f'Access must be one of: {legal}')
    if value == 'none':
        value = None
    return value

def _column_decl_validate(value: list[str]):
    res = []
    for item in value:
        try:
            id_, type_, name = item.split(':')
        except ValueError:
            raise typer.BadParameter('Column must be declared as "id:type:label"')
        res.append([id_, type_, name])
    return res

def _record_decl_validate(value: list[str]):
    res = []
    for item in value:
        try:
            k, v = item.split(':')
        except ValueError:
            raise typer.BadParameter(
                'Record must be declared as "col:value col:value ..."')
        res.append([k, v])
    return res

def _variadic_options_validate(value: list[str]):
    try:
        return dict(zip(*[iter([i.strip('--') for i in value])]*2, strict=True))
    except ValueError:
        raise typer.BadParameter('Improper use of extra option(s)')

def _upload_path_validate(value: Path):
    if not value.is_file():
        raise typer.BadParameter(f'File does not exist: {value}')
    return value

def _upload_pathlist_validate(value: list[Path]):
    for item in value:
        _ = _upload_path_validate(item)
    return value

def _download_path_validate(value: Path):
    if not value.parent.is_dir():
        raise typer.BadParameter(f'Path does not exist: {value}')
    return value

# a few recurrent Typer options
# ----------------------------------------------------------------------
_verbose_opt = typer.Option('--verbose', '-v', count=True,
                            help='Verbose level (0-2)')
_quiet_opt = typer.Option('--quiet', '-q', help='All output will be suppressed')
_inspect_opt = typer.Option('--inspect', '-i', 
                            help = 'Print inspect output after api call')
_user_id_arg = typer.Argument(help='The user ID')
_sacc_id_arg = typer.Argument(help='The service account ID')
_team_id_opt = typer.Option('--team', '-t', 
                            help='The team ID [default: current]')
_ws_id_opt = typer.Option('--workspace', '-w', 
                          help='The workspace integer ID (0 means current)')
_doc_id_opt = typer.Option('--document', '-d', 
                           help='The document ID [default: current]')
_table_id_opt = typer.Option('--table', '-b',  help='The table ID name', 
                             prompt='Insert the table ID name') 
_access_opt = typer.Option('--access', '-a', 
                           help='The new access level',
                           prompt='Insert the new access level',
                           callback=_user_access_validate)
_max_access_opt = typer.Option('--max-access', '-A', 
                               help='The max inherited access level',
                               callback=_user_max_access_validate)
_pinned_opt = typer.Option('--pinned/--no-pinned', '-P/-p', help='Is pinned')
_hidden_opt = typer.Option('--hidden/--no-hidden', '-H/-h', 
                           help='Include hidden cols')
_limit_opt = typer.Option('--limit', '-l', 
                          help='Return at most this number of rows.')
_sort_opt = typer.Option('--sort', '-s', 
                         help='Order in which to return results.')
_noparse_opt = typer.Option('--noparse', 
                            help='True prohibits parsing according to col type')
_outmode_opt = typer.Option('--output-mode', '-m', help='Output type')
_enable_opt = typer.Option('--enable/--disable', help='Enable/disable')

# Typer sub-commands
# ----------------------------------------------------------------------
user_app = typer.Typer(help='Manage users, SCIM must be enabled')
cuser_app = typer.Typer(help='Manage current user, session and apy key')
org_app = typer.Typer(help='Manage Grist teams, aka organisations')
ws_app = typer.Typer(help='Manage workspaces inside a team site')
doc_app = typer.Typer(help='Manage documents inside a workspace')
table_app = typer.Typer(help='Manage tables inside a document')
col_app = typer.Typer(help='Manage columns inside a table')
rec_app = typer.Typer(help='Manage records inside a table')
att_app = typer.Typer(help='Manage attachments and attachment storage')
hook_app = typer.Typer(help='Manage document webhooks')
scim_app = typer.Typer(help='Metadata about SCIM services, if enabled')
sacc_app = typer.Typer(help='Manage service accounts, if enabled')
_help = 'Gry, a command line tool for the Grist API - powered by Pygrister'
_epilog = 'Learn more: https://pygrister.readthedocs.io - https://github.com/ricpol/pygrister '
app = typer.Typer(no_args_is_help=True, help=_help, epilog=_epilog)
app.add_typer(sacc_app, name='sacc', no_args_is_help=True)
app.add_typer(cuser_app, name='cuser', no_args_is_help=True)
app.add_typer(user_app, name='user', no_args_is_help=True)
app.add_typer(org_app, name='team', no_args_is_help=True)
app.add_typer(ws_app, name='ws', no_args_is_help=True)
app.add_typer(doc_app, name='doc', no_args_is_help=True)
app.add_typer(table_app, name='table', no_args_is_help=True)
app.add_typer(col_app, name='col', no_args_is_help=True)
app.add_typer(rec_app, name='rec', no_args_is_help=True)
app.add_typer(att_app, name='att', no_args_is_help=True)
app.add_typer(hook_app, name='hook', no_args_is_help=True)
app.add_typer(scim_app, name='scim', no_args_is_help=True)

# gry version
# ----------------------------------------------------------------------
@app.command('version')
def gryversion() -> None:
    """Prints Pygrister/Gry version"""
    cli_console.print(__version__)

# gry test -> a quick configuration check
# ----------------------------------------------------------------------
@app.command('test')
def grytest() -> None:
    """Run a quick configuration test for your Gry console"""
    tests = {
        'connection': 'skipped', 
        'scim enabled': 'skipped',
        'default ws': 'skipped',
        'default team': 'skipped', 
        'default doc': 'skipped', 
        'store type': 'skipped',
        }
    abort = False
    content = Table('test', 'result')
    try:
        st, res = grist_api.see_team()
    except RequestException as e:
        tests['connection'] = str(e)
        abort = True
    if not abort and st == 401: # invalid api key
        tests['connection'] = str(res)
        abort = True # no sense in going on
    if not abort:
        tests['connection'] = 'ok'
        if st == 200:
            tests['default team'] = 'ok'
        else:
            tests['default team'] = str(res)
        st, res = grist_api.see_myself()
        tests['scim enabled'] = 'yes' if st == 200 else str(res)
        st, res = grist_api.see_workspace()
        tests['default ws'] = 'ok' if st == 200 else str(res)
        if tests['default team'] == 'ok':
            st, res = grist_api.see_doc()
            tests['default doc'] = 'ok' if st == 200 else str(res)
        if tests['default doc'] == 'ok':
            st, res = grist_api.see_attachment_store()
            tests['store type'] = str(res)
    for key, value in tests.items():
        content.add_row(key, value)
    cli_console.print(content)

# gry conf -> print the current Grist configuration
# ----------------------------------------------------------------------
@app.command('conf')
def gryconf(showkey: Annotated[bool, 
                typer.Option('--show-apikey/--hide-apikey', '-K/-k', 
                help='Show in full or obfuscate apikey')] = False) -> None:
    """Print current Gry configuration and additional Requests options"""
    res = grist_api.configurator.config
    if not showkey:
        res['GRIST_API_KEY'] = apikey2output(res['GRIST_API_KEY'])
    table = Table('key', 'value')
    for k, v in res.items():
        table.add_row(k, str(v))
    table.add_section()
    for k, v in grist_api.apicaller.request_options.items():
        table.add_row(k, str(v))
    cli_console.print(table)

# gry sql -> post SELECT sql queries to Grist
# ----------------------------------------------------------------------
@app.command('sql')
def run_sql(
    statement: Annotated[str, typer.Argument(
                         help='The sql statement - SELECT only')],
    params: Annotated[Optional[List[str]], typer.Option('--param', '-p',
                      help='Query parameters')] = None,
    timeout: Annotated[int, typer.Option('--timeout', '-t', 
                       help='Query timeout')] = 1000,
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Run a SELECT sql query against the document. 
    
    Repeat PARAM for multiple parameters, eg:
    
    % gry sql "select (...) where x>? and x<?;" -p 10 -p 100"""
    if params:
        st, res = grist_api.run_sql_with_args(statement, params, timeout, 
                                              doc_id, team_id)
    else:
        st, res = grist_api.run_sql(statement, doc_id, team_id)
    if not _exit_early(st, res, quiet, verbose, inspect):
        if res:
            content = Table(*res[0].keys())
            for row in res:
                content.add_row(*[str(v) for v in row.values()])
        else:
            content = 'No records found.'
        cli_console.print(content)

# gry python -> open a Gry-aware Python shell
# ----------------------------------------------------------------------
@app.command('python')
def open_python(idle: Annotated[bool, typer.Option('--idle', 
                                help='Open the Idle shell')] = False):
    """Open a Python shell with Pygrister pre-loaded"""
    if standalone:
        cli_console.print("'gry python' is not currently available in standalone Gry")
        return
    start = Path(__file__).absolute().parent / '_pygrystart.py'
    oldstartup = os.environ.get('PYTHONSTARTUP', None)
    os.environ['PYTHONSTARTUP'] = str(start)
    if idle:
        to_run = [sys.executable, '-m', 'idlelib', '-s']
    else:
        to_run = [sys.executable, '-q']
    try:
        subprocess.run(to_run)
    finally:
        if oldstartup:
            os.environ['PYTHONSTARTUP'] = oldstartup
        print('Done. Welcome back to Gry.')

# gry sacc -> service accounts, set GRIST_ENABLE_SERVICE_ACCOUNTS on server
# ----------------------------------------------------------------------

@sacc_app.command('list')
def list_saccs(quiet: Annotated[bool, _quiet_opt] = False,
               verbose: Annotated[int, _verbose_opt] = 0,
               inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """List all service accounts"""
    st, res = grist_api.list_service_accounts()
    if not _exit_early(st, res, quiet, verbose, inspect):
        if res:
            content = Table('key', 'value')
            for account in res:
                content = _make_sacc_data(account, content)
        else:
            content = 'No service accounts available.'
        cli_console.print(content)

@sacc_app.command('see')
def see_sacc(sacc: Annotated[int, _sacc_id_arg],
             quiet: Annotated[bool, _quiet_opt] = False,
             verbose: Annotated[int, _verbose_opt] = 0,
             inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Retrieve service account by ID"""
    st, res = grist_api.see_service_account(sacc)
    if not _exit_early(st, res, quiet, verbose, inspect):
        content = Table('key', 'value')
        content = _make_sacc_data(res, content)
        cli_console.print(content)

@sacc_app.command('new')
def new_sacc(
    expire: Annotated[str, typer.Argument(help="Expire date YYYY-MM-DD")],
    label: Annotated[str, typer.Option('--label', help='Label')] = '',
    description: Annotated[str, typer.Option('--description', help='Description')] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Add a service account (WARNING: key will be displayed)"""
    st, res = grist_api.add_service_account(expire, label, description)
    if not _exit_early(st, res, quiet, verbose, inspect):
        output = f'{res[0]} (key: {res[1]})'
        cli_console.print(DONEMSG, 'Id:', output)

@sacc_app.command('update')
def update_sacc(
    sacc: Annotated[int, _sacc_id_arg],
    expire: Annotated[str, typer.Option('--expire', help="Expire date YYYY-MM-DD")] = '',
    label: Annotated[str, typer.Option('--label', help='Label')] = '',
    description: Annotated[str, typer.Option('--description', help='Description')] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Update a service account"""
    st, res = grist_api.update_service_account(sacc, expire, label, description)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@sacc_app.command('delete')
def delete_sacc(sacc: Annotated[int, _sacc_id_arg],
                quiet: Annotated[bool, _quiet_opt] = False,
                verbose: Annotated[int, _verbose_opt] = 0,
                inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Remove a service account"""
    st, res = grist_api.delete_service_account(sacc)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@sacc_app.command('new-key')
def update_sacc_key(sacc: Annotated[int, _sacc_id_arg],
                    quiet: Annotated[bool, _quiet_opt] = False,
                    verbose: Annotated[int, _verbose_opt] = 0,
                    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Regenerate a service account's key (WARNING: key will be displayed)"""
    st, res = grist_api.update_service_account_key(sacc)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@sacc_app.command('delete-key')
def delete_sacc_key(sacc: Annotated[int, _sacc_id_arg],
                    quiet: Annotated[bool, _quiet_opt] = False,
                    verbose: Annotated[int, _verbose_opt] = 0,
                    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Delete a service account's key"""
    st, res = grist_api.delete_service_account_key(sacc)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

# gry cuser -> current user, session and api key
# ----------------------------------------------------------------------

@cuser_app.command('see')
def see_profile(quiet: Annotated[bool, _quiet_opt] = False,
                verbose: Annotated[int, _verbose_opt] = 0,
                inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Retrieve information on current user profile"""
    st, res = grist_api.see_profile()
    _exit_early_or_print_content(st, res, quiet, verbose, inspect)

@cuser_app.command('update')
def update_profile(
    name: Annotated[str, typer.Option('--name', '-n', 
                                      help='New user name')] = '', 
    locale: Annotated[str, typer.Option('--locale', '-l', 
                      help='New user locale (None to reset)')] = '', 
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Change current user name or locale"""
    if name and locale:
        raise typer.BadParameter('You cannot set both name and locale options')
    if name:
        st, res = grist_api.update_profile_name(name)
        _exit_early_or_print_done(st, res, quiet, verbose, inspect)
        return
    if locale:
        if locale in ('None', 'none'): 
            locale = ''
        st, res = grist_api.update_profile_locale(locale)
        _exit_early_or_print_done(st, res, quiet, verbose, inspect)
        return
    raise typer.BadParameter('You must set either name or locale option')

@cuser_app.command('session')
def see_session(quiet: Annotated[bool, _quiet_opt] = False,
                verbose: Annotated[int, _verbose_opt] = 0,
                inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Retrieve information about current session"""
    st, res = grist_api.see_session()
    _exit_early_or_print_content(st, res, quiet, verbose, inspect)

@cuser_app.command('users')
def session_users(quiet: Annotated[bool, _quiet_opt] = False,
                  verbose: Annotated[int, _verbose_opt] = 0,
                  inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Retrieve information about all session users"""
    st, res = grist_api.see_session_users()
    _exit_early_or_print_content(st, res, quiet, verbose, inspect)

@cuser_app.command('set-active')
def change_session_user(email: Annotated[str, typer.Argument(help='User email')], 
                        team_id: Annotated[str, _team_id_opt] = '',
                        quiet: Annotated[bool, _quiet_opt] = False,
                        verbose: Annotated[int, _verbose_opt] = 0,
                        inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Switch active session user"""
    team = team_id or 'current'
    st, res = grist_api.update_session_user(email, team)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@cuser_app.command('apikey')
def see_change_apikey(new: Annotated[bool, typer.Option('--new', '-n', 
                                            help='Generate new key')] = False, 
                      quiet: Annotated[bool, _quiet_opt] = False,
                      verbose: Annotated[int, _verbose_opt] = 0,
                      inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """See or generate new Api key (WARNING: key will be displayed)"""
    if new:
        st, res = grist_api.new_apikey()
    else:
        st, res = grist_api.see_apikey()
    _exit_early_or_print_content(st, res, quiet, verbose, inspect)

@cuser_app.command('del-apikey')
def del_apikey(quiet: Annotated[bool, _quiet_opt] = False,
               verbose: Annotated[int, _verbose_opt] = 0,
               inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Delete Api key (DANGER: no further Api call will be possible!)"""
    st, res = grist_api.delete_apikey()
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

# gry user -> for managing users with SCIM apis
# ----------------------------------------------------------------------
@user_app.command('list')
def list_users(
    start: Annotated[int, typer.Option('--start', '-s', 
                     help='First ID to retrieve')] = 1,
    retrieve: Annotated[int, typer.Option('--retrieve', '-r', 
                        help='Max users to retrieve')] = 10,
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """List users. No filter option available"""
    st, res = grist_api.list_users_raw(start, retrieve)
    if not _exit_early(st, res, quiet, verbose, inspect):
        if start > res['totalResults']:
            content = 'No users.'
        else:
            content = Table('key', 'value')
            for user in res['Resources']:
                content = _make_scim_user_data(user, content)
        cli_console.print(content)

@user_app.command('me')
def see_me(quiet: Annotated[bool, _quiet_opt] = False,
           verbose: Annotated[int, _verbose_opt] = 0,
           inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Retrieve information about oneself"""
    st, res = grist_api.see_myself()
    if not _exit_early(st, res, quiet, verbose, inspect):
        content = Table('key', 'value')
        content = _make_scim_user_data(res, content)
        cli_console.print(content)

@user_app.command('see')
def see_user(user: Annotated[int, _user_id_arg],
             quiet: Annotated[bool, _quiet_opt] = False,
             verbose: Annotated[int, _verbose_opt] = 0,
             inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Retrieve user by ID"""
    st, res = grist_api.see_user(user)
    if not _exit_early(st, res, quiet, verbose, inspect):
        content = Table('key', 'value')
        content = _make_scim_user_data(res, content)
        cli_console.print(content)
    
@user_app.command('new')
def new_user(
    name: Annotated[str, typer.Argument(help="User name")],
    email: Annotated[str, typer.Argument(help='User email')],
    display: Annotated[str, typer.Option('--display', '-d', 
                       help='User display name')] = '',
    formatted: Annotated[str, typer.Option('--formatted', '-f', 
                         help='User formatted name')] = '',
    lang: Annotated[str, typer.Option('--language', '-g', 
                    help='User language')] = 'en', 
    locale: Annotated[str, typer.Option('--locale', '-l', 
                      help='User locale')] = 'en',
    picture: Annotated[str, typer.Option('--picture', '-p', 
                       help='User picture url')] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Add a user"""
    photos = [picture] if picture else None
    st, res = grist_api.add_user(name, [email], formatted, display, lang, 
                                 locale, photos) 
    _exit_early_or_print_id(st, res, quiet, verbose, inspect)

class _OperationTypes(str, Enum):
    add = 'add'
    repl = 'replace'
    remove = 'remove'

@user_app.command('update')
def update_user(
    user_id: Annotated[int, typer.Argument(help="User ID")],
    op_path: Annotated[str, typer.Argument(help="Operation path")],
    op_value: Annotated[str, typer.Argument(help="Operation value")],
    operation: Annotated[_OperationTypes, typer.Option('--operation', '-o',         
                         help="Operation to perform")] = _OperationTypes.repl,
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Update a user. Only one update operation is possible"""
    op = {'op': operation, 'path': op_path, 'value': op_value}
    st, res = grist_api.update_user(user_id, [op])
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@user_app.command('delete')
def delete_user(user: Annotated[int, _user_id_arg],
                quiet: Annotated[bool, _quiet_opt] = False,
                verbose: Annotated[int, _verbose_opt] = 0,
                inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Remove a user"""
    st, res = grist_api.delete_user(user)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@user_app.command('enable')
def enable_user(user: Annotated[int, _user_id_arg],
                enable: Annotated[bool, _enable_opt] = True,
                quiet: Annotated[bool, _quiet_opt] = False,
                verbose: Annotated[int, _verbose_opt] = 0,
                inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Enable or disable a user"""
    st, res = grist_api.enable_user(user, enable)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

# TODO we don't implement "search" for now because we don't have a good way 
# to express filters in the shell. 

# gry scim -> metadata about SCIM service
# ----------------------------------------------------------------------
@scim_app.command('schemas')
def scim_schemas(quiet: Annotated[bool, _quiet_opt] = False,
                 verbose: Annotated[int, _verbose_opt] = 0,
                 inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Retrieve SCIM schemas"""
    st, res = grist_api.see_scim_schemas()
    _exit_early_or_print_content(st, res, quiet, verbose, inspect)

@scim_app.command('config')
def scim_config(quiet: Annotated[bool, _quiet_opt] = False,
                verbose: Annotated[int, _verbose_opt] = 0,
                inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Retrieve SCIM configuration"""
    st, res = grist_api.see_scim_config()
    _exit_early_or_print_content(st, res, quiet, verbose, inspect)

@scim_app.command('resources')
def scim_resources(quiet: Annotated[bool, _quiet_opt] = False,
                   verbose: Annotated[int, _verbose_opt] = 0,
                   inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Retrieve SCIM resources"""
    st, res = grist_api.see_scim_resources()
    _exit_early_or_print_content(st, res, quiet, verbose, inspect)

# gry team -> for managing team sites (organisations)
# ----------------------------------------------------------------------
@org_app.command('list')
def list_orgs(quiet: Annotated[bool, _quiet_opt] = False,
              verbose: Annotated[int, _verbose_opt] = 0,
              inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """List the teams you have access to"""
    st, res = grist_api.list_team_sites()
    if not _exit_early(st, res, quiet, verbose, inspect):
        content = Table('id', 'name', 'owner')
        for org in res:
            try:
                owner = org['owner']['name']
            except TypeError:
                owner = 'Null'
            content.add_row(str(org['id']), org['name'], owner)
        cli_console.print(content)

@org_app.command('see')
def see_org(team_id: Annotated[str, _team_id_opt] = '', 
            quiet: Annotated[bool, _quiet_opt] = False,
            verbose: Annotated[int, _verbose_opt] = 0,
            inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Describe a team"""
    st, res = grist_api.see_team(team_id)
    if not _exit_early(st, res, quiet, verbose, inspect):
        content = Table('key', 'value')
        content.add_row('id', str(res['id']))
        content.add_row('name', res['name'])
        content.add_row('domain', res['domain'])
        try:
            row = f"{res['owner']['id']} - {res['owner']['name']}"
        except TypeError:
            row = 'None'
        content.add_row('owner', row)
        cli_console.print(content)

@org_app.command('usage')
def usage_org(team_id: Annotated[str, _team_id_opt] = '', 
              quiet: Annotated[bool, _quiet_opt] = False,
              verbose: Annotated[int, _verbose_opt] = 0,
              inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Details a team usage summary"""
    st, res = grist_api.see_team_usage(team_id)
    if not _exit_early(st, res, quiet, verbose, inspect):
        content = Table('key', 'value')
        content.add_row('appr. limit', 
                        str(res['countsByDataLimitStatus']['approachingLimit']))
        content.add_row('grace period', 
                        str(res['countsByDataLimitStatus']['gracePeriod']))
        content.add_row('delete only', 
                        str(res['countsByDataLimitStatus']['deleteOnly']))
        content.add_row('att. tot. bytes', 
                        str(res['attachments']['totalBytes']))
        #TODO not yet available?
        #content.add_row('att. limit exceeded', str(res['attachments']['limitExceeded']))
        cli_console.print(content)

@org_app.command('update')
def update_org(name: Annotated[str, typer.Argument(help='The new name')], 
               team_id: Annotated[str, _team_id_opt] = '',
               quiet: Annotated[bool, _quiet_opt] = False,
               verbose: Annotated[int, _verbose_opt] = 0,
               inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Change the team name"""
    st, res = grist_api.update_team(name, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)
     
@org_app.command('delete')
def delete_org(team_id: Annotated[str, _team_id_opt] = '',
               quiet: Annotated[bool, _quiet_opt] = False,
               verbose: Annotated[int, _verbose_opt] = 0,
               inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Delete a team"""
    st, res = grist_api.delete_team(team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@org_app.command('users')
def list_org_users(team_id: Annotated[str, _team_id_opt] = '',  
                   quiet: Annotated[bool, _quiet_opt] = False,
                   verbose: Annotated[int, _verbose_opt] = 0,
                   inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """List users with access to team"""
    st, res = grist_api.list_team_users(team_id)
    if not _exit_early(st, res, quiet, verbose, inspect):
        content = _make_user_table(res)
        cli_console.print(content)

@org_app.command('user-access')
def change_team_access(uid: Annotated[int, typer.Argument(help='The user ID')], 
                       access: Annotated[str, _access_opt],
                       team_id: Annotated[str, _team_id_opt] = '',
                       quiet: Annotated[bool, _quiet_opt] = False,
                       verbose: Annotated[int, _verbose_opt] = 0,
                       inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Change user access level to a team"""
    st, res = grist_api.list_team_users(team_id)
    if not _exit_early(st, res, quiet, 0, inspect):
        usr_email = ''
        for usr in res:
            if usr['id'] == uid:
                usr_email = usr['email']
                break
        if not usr_email:
            if inspect:
                cli_console.print(grist_api.inspect())
                cli_console.rule()
            raise typer.BadParameter('User id not found.')
        users = {usr_email: access}
        st, res = grist_api.update_team_users(users, team_id)
        _exit_early_or_print_done(st, res, quiet, verbose, inspect)
        
#TODO "change_user_access" is only for existing users, but "update_team_users"
# allows for adding users too. Maybe add a separate cli endpoint for this?

# gry ws -> for managing workspaces
# ----------------------------------------------------------------------
@ws_app.command('list')
def list_ws(team_id: Annotated[str, _team_id_opt] = '', 
            quiet: Annotated[bool, _quiet_opt] = False,
            verbose: Annotated[int, _verbose_opt] = 0,
            inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """List workspaces and documents in a team"""
    st, res = grist_api.list_workspaces(team_id)
    if not _exit_early(st, res, quiet, verbose, inspect):
        content = Table('id', 'name', 'owner', 'email', 'docs')
        for ws in res:
            try:
                owner = str(ws['owner']['id'])
            except TypeError:
                owner = 'Null'
            try:
                email = ws['owner']['email']
            except TypeError:
                email = ''
            numdocs = len(ws.get('docs', []))
            content.add_row(str(ws['id']), ws['name'], 
                            owner, email, str(numdocs))
        cli_console.print(content)

@ws_app.command('see')
def see_ws(ws_id: Annotated[int, _ws_id_opt] = 0,
           quiet: Annotated[bool, _quiet_opt] = False,
           verbose: Annotated[int, _verbose_opt] = 0,
           inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Describe a workspace"""
    st, res = grist_api.see_workspace(ws_id)
    if not _exit_early(st, res, quiet, verbose, inspect):
        content = Table('key', 'value')
        content.add_row('id', str(res['id']))
        content.add_row('name', res['name'])
        try:
            row = f"{res['org']['id']} - {res['org']['name']}"
        except TypeError:
            row = 'Null'
        content.add_row('team', row)
        content.add_section()
        for doc in res.get('docs', []):
            content.add_row('doc', f"{doc['id']} - {doc['name']}")
        cli_console.print(content)

@ws_app.command('new')
def add_ws(name: Annotated[str, typer.Argument(help='The name of new workspace')], 
           team_id: Annotated[str, _team_id_opt] = '',
           quiet: Annotated[bool, _quiet_opt] = False,
           verbose: Annotated[int, _verbose_opt] = 0,
           inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Create an empty workspace"""
    st, res = grist_api.add_workspace(name, team_id)
    _exit_early_or_print_id(st, res, quiet, verbose, inspect)

@ws_app.command('update')
def update_ws(name: Annotated[str, typer.Argument(help='The new name')], 
              ws_id: Annotated[int, _ws_id_opt] = 0,
              quiet: Annotated[bool, _quiet_opt] = False,
              verbose: Annotated[int, _verbose_opt] = 0,
              inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Change the workspace name"""
    st, res = grist_api.update_workspace(name, ws_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@ws_app.command('delete')
def delete_ws(ws_id: Annotated[int, _ws_id_opt] = 0,
              quiet: Annotated[bool, _quiet_opt] = False,
              verbose: Annotated[int, _verbose_opt] = 0,
              inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Delete a workspace"""
    st, res = grist_api.delete_workspace(ws_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@ws_app.command('trash')
def trash_ws(
    remove: Annotated[bool, typer.Option('--remove/--restore', '-R/-r', 
                      help='Move to trash or restore')] = True, 
    permanent: Annotated[bool, typer.Option('--permanent', 
                         help='Remove permanently')] = False,
    ws_id: Annotated[int, _ws_id_opt] = 0,
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Move to trash or restore a workspace"""
    st, res = grist_api.trash_workspace(remove, permanent, ws_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@ws_app.command('users')
def list_ws_users(ws_id: Annotated[int, _ws_id_opt] = 0,  
                  quiet: Annotated[bool, _quiet_opt] = False,
                  verbose: Annotated[int, _verbose_opt] = 0,
                  inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """List users with access to workspace"""
    st, res = grist_api.list_workspace_users(ws_id)
    if not _exit_early(st, res, quiet, verbose, inspect):
        content = _make_user_table(res)
        cli_console.print(content)

@ws_app.command('user-access')
def change_ws_access(uid: Annotated[int, typer.Argument(help='The user ID')], 
                     access: Annotated[str, _access_opt],
                     ws_id: Annotated[int, _ws_id_opt] = 0,
                     quiet: Annotated[bool, _quiet_opt] = False,
                     verbose: Annotated[int, _verbose_opt] = 0,
                     inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Change user access level to a workspace"""
    st, res = grist_api.list_workspace_users(ws_id)
    if not _exit_early(st, res, quiet, 0, inspect):
        usr_email = ''
        for usr in res:
            if usr['id'] == uid:
                usr_email = usr['email']
                break
        if not usr_email:
            if inspect:
                cli_console.print(grist_api.inspect())
                cli_console.rule()
            raise typer.BadParameter('User id not found.')
        users = {usr_email: access}
        st, res = grist_api.update_workspace_users(users, ws_id)
        _exit_early_or_print_done(st, res, quiet, verbose, inspect)
        
#TODO "change_ws_access" is only for existing users, but "update_team_users"
# allows for adding users too. Maybe add a separate cli endpoint for this?

# gry doc -> for managing documents
# ----------------------------------------------------------------------
@doc_app.command('see')
def see_doc(doc_id: Annotated[str, _doc_id_opt] = '', 
            team_id: Annotated[str, _team_id_opt] = '',
            quiet: Annotated[bool, _quiet_opt] = False,
            verbose: Annotated[int, _verbose_opt] = 0,
            inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Describe a document"""
    st, res = grist_api.see_doc(doc_id, team_id)
    if not _exit_early(st, res, quiet, verbose, inspect):
        content = Table('key', 'value')
        content.add_row('id', res['id'])
        content.add_row('name', res['name'])
        content.add_row('pinned', str(res['isPinned']))
        try:
            row = f"{res['workspace']['id']} - {res['workspace']['name']}"
        except TypeError:
            row = 'Null'
        content.add_row('workspace', row)
        try:
            row = f"{res['workspace']['org']['id']} - {res['workspace']['org']['name']}"
        except TypeError:
            row = 'Null'
        content.add_row('team', row)
        cli_console.print(content)

@doc_app.command('new')
def add_doc(name: Annotated[str, typer.Argument(help='The name of new doc')], 
            pinned: Annotated[bool, _pinned_opt] = False,
            ws_id: Annotated[int, _ws_id_opt] = 0, 
            quiet: Annotated[bool, _quiet_opt] = False,
            verbose: Annotated[int, _verbose_opt] = 0,
            inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Create an empty document"""
    st, res = grist_api.add_doc(name, pinned, ws_id)
    _exit_early_or_print_id(st, res, quiet, verbose, inspect)

@doc_app.command('update')
def update_doc(name: Annotated[str, typer.Argument(help='The new name')],
               pinned: Annotated[bool, _pinned_opt] = False,
               doc_id: Annotated[str, _doc_id_opt] = '', 
               team_id: Annotated[str, _team_id_opt] = '',
               quiet: Annotated[bool, _quiet_opt] = False,
               verbose: Annotated[int, _verbose_opt] = 0,
               inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Modify document metadata"""
    st, res = grist_api.update_doc(name, pinned, doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@ doc_app.command('move')
def move_doc(dest: Annotated[int, typer.Argument(help='Destination workspace ID')],
             doc_id: Annotated[str, _doc_id_opt] = '', 
             team_id: Annotated[str, _team_id_opt] = '',
             quiet: Annotated[bool, _quiet_opt] = False,
             verbose: Annotated[int, _verbose_opt] = 0,
             inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Move document to another workspace"""
    st, res = grist_api.move_doc(dest, doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@ doc_app.command('copy')
def copy_doc(
    dest: Annotated[int, typer.Argument(help='Destination workspace ID')],
    name: Annotated[str, typer.Argument(help='Target doc name')],
    template: Annotated[bool,typer.Option('--template', 
                        help='Copy as template')] = False,             
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Copy document to another workspace"""
    st, res = grist_api.copy_doc(dest, name, template, doc_id, team_id)
    _exit_early_or_print_id(st, res, quiet, verbose, inspect)

@doc_app.command('delete')
def delete_doc(doc_id: Annotated[str, _doc_id_opt] = '', 
               team_id: Annotated[str, _team_id_opt] = '',
               quiet: Annotated[bool, _quiet_opt] = False,
               verbose: Annotated[int, _verbose_opt] = 0,
               inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Delete a document"""
    st, res = grist_api.delete_doc(doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@doc_app.command('trash')
def trash_doc(
    remove: Annotated[bool, typer.Option('--remove/--restore', '-R/-r', 
                      help='Move to trash or restore')] = True, 
    permanent: Annotated[bool, typer.Option('--permanent', 
                         help='Remove permanently')] = False,
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Move to trash or restore a document"""
    st, res = grist_api.trash_doc(remove, permanent, doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@doc_app.command('purge-history')
def delete_doc_history(
    keep: Annotated[int, typer.Option('--keep', '-k', 
                    help='Latest actions to keep')] = 0,
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Delete the document action history"""
    st, res = grist_api.delete_doc_history(keep, doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@doc_app.command('reload')
def reload_doc(doc_id: Annotated[str, _doc_id_opt] = '', 
               team_id: Annotated[str, _team_id_opt] = '',
               quiet: Annotated[bool, _quiet_opt] = False,
               verbose: Annotated[int, _verbose_opt] = 0,
               inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Reload a document"""
    st, res = grist_api.reload_doc(doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@doc_app.command('enable')
def enable_doc(enable: Annotated[bool, _enable_opt] = True,
               doc_id: Annotated[str, _doc_id_opt] = '', 
               team_id: Annotated[str, _team_id_opt] = '',
               quiet: Annotated[bool, _quiet_opt] = False,
               verbose: Annotated[int, _verbose_opt] = 0,
               inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Ebable or disable a document"""
    st, res = grist_api.enable_doc(enable, doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@doc_app.command('pin')
def pin_doc(
    pin: Annotated[bool, typer.Option('--pin/--unpin', help='Pin/unpin')] = True,
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Pin or unpin a document"""
    st, res = grist_api.pin_doc(pin, doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@doc_app.command('recovery')
def doc_recovery(
    mode: Annotated[bool, typer.Option('--set/--unset', '-R/-r', 
                    help='Set/unset recovery mode')] = True,
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Controls the recovery mode of a document"""
    st, res = grist_api.set_recovery_mode(mode, doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@doc_app.command('download')
def download_db(
    filename: Annotated[Path, typer.Argument(help='Output file path',
                        callback=_download_path_validate)],
    history: Annotated[bool, typer.Option('--history/--no-history', '-H/-h', 
                       help='Include history')] = False, 
    template: Annotated[bool, typer.Option('--template/--no-template', '-P/-p', 
                        help='Template only, no data')] = False, 
    doc_id: Annotated[str, _doc_id_opt] = '', 
    quiet: Annotated[bool, _quiet_opt] = False,
    team_id: Annotated[str, _team_id_opt] = '',
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Download the document as sqlite file"""
    nohistory = not history
    st, res = grist_api.download_sqlite(filename, nohistory, template, 
                                        doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, 0, inspect) # force verbose=0 in download mode

@doc_app.command('upload')
def upload_doc(
    filename: Annotated[Path, typer.Argument(help='Sqlite file to upload', 
                        callback=_upload_path_validate)],
    docname: Annotated[str, typer.Argument(help='Name of the target document')],
    ws_id: Annotated[int, _ws_id_opt] = 0,
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Import a document from an sqlite file"""
    st, res = grist_api.upload_sqlite(filename, docname, ws_id)
    _exit_early_or_print_id(st, res, quiet, verbose, inspect)

@doc_app.command('users')
def list_doc_users(doc_id: Annotated[str, _doc_id_opt] = '', 
                   team_id: Annotated[str, _team_id_opt] = '',
                   quiet: Annotated[bool, _quiet_opt] = False,
                   verbose: Annotated[int, _verbose_opt] = 0,
                   inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """List users with access to document"""
    st, res = grist_api.list_doc_users(doc_id, team_id)
    if not _exit_early(st, res, quiet, verbose, inspect):
        content = _make_user_table(res)
        cli_console.print(content)

@doc_app.command('user-access')
def change_doc_access(uid: Annotated[int, typer.Argument(help='The user ID')], 
                      access: Annotated[str, _access_opt],
                      max_access: Annotated[str, _max_access_opt] = 'owners', 
                      doc_id: Annotated[str, _doc_id_opt] = '', 
                      team_id: Annotated[str, _team_id_opt] = '',
                      quiet: Annotated[bool, _quiet_opt] = False,
                      verbose: Annotated[int, _verbose_opt] = 0,
                      inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Change user access level to a document"""
    st, res = grist_api.list_doc_users(doc_id, team_id)
    if not _exit_early(st, res, quiet, 0, inspect):
        usr_email = ''
        for usr in res:
            if usr['id'] == uid:
                usr_email = usr['email']
                break
        if not usr_email:
            if inspect:
                cli_console.print(grist_api.inspect())
                cli_console.rule()
            raise typer.BadParameter('User id not found.')
        users = {usr_email: access}
        st, res = grist_api.update_doc_users(users, max_access, doc_id, team_id)
        _exit_early_or_print_done(st, res, quiet, verbose, inspect)

#TODO again, this is for existing users only, but the api 
# allows for adding users too. Maybe add a separate cli endpoint for this?

# gry table -> for managing tables
# ----------------------------------------------------------------------
@table_app.command('list')
def list_tables(doc_id: Annotated[str, _doc_id_opt] = '', 
                team_id: Annotated[str, _team_id_opt] = '',
                quiet: Annotated[bool, _quiet_opt] = False,
                verbose: Annotated[int, _verbose_opt] = 0,
                inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """List tables in a document"""
    st, res = grist_api.list_tables(doc_id, team_id)
    if not _exit_early(st, res, quiet, verbose, inspect):
        content = Table('table id', 'metadata')
        for t in res:
            f = t['fields']
            mdata = '\n'.join([f'{k}: {v}' for k, v in f.items()])
            content.add_row(t['id'], mdata)
            content.add_section()
        cli_console.print(content)

@table_app.command('new')
def new_table(
    cols: Annotated[List[str], typer.Argument(callback=_column_decl_validate,
                    help='Column list, each declared as "id:type:label"')],
    tname: Annotated[str, _table_id_opt], 
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Add one table to a document. 

    Column must be declared as "id:type:label"; type is any valid Grist type:

    % gry table new name:Text:Name age:Int:Age -n People"""
    column_list = []
    for id_, type_, label in cols:
        column_list.append({'id': id_, 
                            'fields': {'type': type_, 'label': label}})
    table = [{'id': tname, 'columns': column_list}]
    st, res = grist_api.add_tables(table, doc_id, team_id)
    if not _exit_early(st, res, quiet, verbose, inspect):
        cli_console.print(f'{DONEMSG} Id: {res[0]}')

@table_app.command('update', context_settings={'allow_extra_args': True, 
                                               'ignore_unknown_options': True})
def update_table(ctx: typer.Context,
                 tname: Annotated[str, _table_id_opt], 
                 doc_id: Annotated[str, _doc_id_opt] = '', 
                 team_id: Annotated[str, _team_id_opt] = '',
                 quiet: Annotated[bool, _quiet_opt] = False,
                 verbose: Annotated[int, _verbose_opt] = 0,
                 inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Update table metadata.
    
    Pass any metadata field as an extra option, eg: 
    
    % gry table update -b Mytable --tableRef 2 --onDemand false"""
    fields = _variadic_options_validate(ctx.args)
    # some more validation 
    valid_keys = ('primaryViewId', 'summarySourceTable', 'onDemand', 
                  'rawViewSectionRef', 'recordCardViewSectionRef')
    for k in fields.keys():
        if k not in valid_keys:
            raise typer.BadParameter(f'Unknown option: {k}')
        if k == 'onDemand':
            if fields[k] not in ('true', 'false'):
                raise typer.BadParameter(f'onDemand option must be "true" or "false"')
        else:
            try:
                fields[k] = int(fields[k])
            except ValueError:
                raise typer.BadParameter(f'Option {k} value must be integer')
    table = [{'id': tname, 'fields': fields}]
    st, res = grist_api.update_tables(table, doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

class _DownloadTableOption(str, Enum):
    xslx = 'xlsx'
    csv = 'csv'
    tsv = 'tsv'
    dsv = 'dsv'
    schema = 'schema'

class _HeaderOption(str, Enum):
    label = 'label'
    colid = 'colId'

@table_app.command('download')
def download_table(
    filename: Annotated[Path, typer.Argument(help='Output file path', 
                        callback=_download_path_validate)],
    tname: Annotated[str, _table_id_opt], 
    output: Annotated[_DownloadTableOption, _outmode_opt] = _DownloadTableOption.csv,
    header: Annotated[_HeaderOption, typer.Option('--header', '-h', 
                      help='Column headers')] = _HeaderOption.label,
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Dumps content or schema of a table to FILENAME"""
    if output == _DownloadTableOption.schema:
        st, res = grist_api.download_schema(tname, header, filename, 
                                            doc_id, team_id)
    else:
        st, res = grist_api.download_table(filename, tname, header, 
                                           output.value, doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, 0, inspect) # force verbose=0 in download mode

# gry col -> for managing columns
# ----------------------------------------------------------------------
@col_app.command('list')
def list_columns(
    table: Annotated[str, _table_id_opt],
    hidden: Annotated[bool, _hidden_opt] = False,
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """List columns in a table"""
    st, res = grist_api.list_cols(table, hidden, doc_id, team_id)
    if not _exit_early(st, res, quiet, verbose, inspect):
        content = Table('column id', 'metadata')
        for c in res:
            f = c['fields']
            useful_fields = ['label', 'type', 'isFormula', 'formula']
            mdata = '\n'.join([f'{i}: {str(f[i])}' for i in useful_fields ])
            content.add_row(c['id'], mdata)
            content.add_section()
        cli_console.print(content)

@col_app.command('new')
def add_column(
    cols: Annotated[List[str], typer.Argument(callback=_column_decl_validate,
                    help='Column list, each declared as "id:type:label"')],
    table: Annotated[str, _table_id_opt],
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Add columns to a table.
    
    Column must be declared as "id:type:label"; type is any valid Grist type:

    % gry col new name:Text:Name age:Int:Age -b MyTable"""
    columns = []
    for id_, type_, label in cols:
        columns.append({'id': id_, 
                        'fields': {'type': type_, 'label': label}})
    st, res = grist_api.add_cols(table, columns, doc_id, team_id)
    _exit_early_or_print_id(st, res, quiet, verbose, inspect)

@col_app.command('update')
def update_column(
    cols: Annotated[List[str], typer.Argument(callback=_column_decl_validate,
                    help='Column list, each declared as "id:type:label"')],
    table: Annotated[str, _table_id_opt],
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Update columns in a table.
    
    Column must be declared as "id:type:label"; type is any valid Grist type:

    % gry col update name:Text:Name age:Int:Age -b MyTable"""
    columns = []
    for id_, type_, label in cols:
        columns.append({'id': id_, 
                        'fields': {'type': type_, 'label': label}})
    st, res = grist_api.update_cols(table, columns, doc_id, team_id)
    _exit_early_or_print_id(st, res, quiet, verbose, inspect)

# Note: we don't cover add_update_cols (the PUT api) because it is too 
# sophisticated for our very limited way of describing a column in the cli

@col_app.command('delete')
def delete_column(
    col: Annotated[str, typer.Argument(help='Name ID of the column to delete')],
    table: Annotated[str, _table_id_opt],
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Delete a column"""
    st, res = grist_api.delete_column(table, col, doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

# gry rec -> for managing records
# ----------------------------------------------------------------------
@rec_app.command('list')
def list_records(table: Annotated[str, _table_id_opt],
                 sort: Annotated[str, _sort_opt] = '',
                 limit: Annotated[int, _limit_opt] = 0,
                 hidden: Annotated[bool, _hidden_opt] = False,
                 doc_id: Annotated[str, _doc_id_opt] = '', 
                 team_id: Annotated[str, _team_id_opt] = '',
                 quiet: Annotated[bool, _quiet_opt] = False,
                 verbose: Annotated[int, _verbose_opt] = 0,
                 inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Fetch records from a table.
    
    No filter option is available here: 'gry sql' may be a better try."""
    st, res = grist_api.list_records(table, sort=sort, limit=limit, 
                            hidden=hidden, doc_id=doc_id, team_id=team_id)
    if not _exit_early(st, res, quiet, verbose, inspect):
        if res:
            content = Table(*res[0].keys())
            for row in res:
                content.add_row(*[str(v) for v in row.values()])
        else:
            content = 'No records found.'
        cli_console.print(content)
    
@rec_app.command('new')
def add_record(
    record: Annotated[List[str], typer.Argument(callback=_record_decl_validate,
                      help='One record, declared as "col:value col:value ..."')],
    table: Annotated[str, _table_id_opt],
    noparse: Annotated[bool, _noparse_opt] = False,
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Add one record to a table"""
    record = dict(record) # type: ignore
    st, res = grist_api.add_records(table, [record], noparse, doc_id, team_id) # type: ignore
    if not _exit_early(st, res, quiet, verbose, inspect):
        cli_console.print(f'{DONEMSG} Id: {res[0]}')

@rec_app.command('update')
def update_record(
    record: Annotated[List[str], typer.Argument(callback=_record_decl_validate,
                      help='One record, declared as "id:value col:value ..."')],
    table: Annotated[str, _table_id_opt],
    noparse: Annotated[bool, _noparse_opt] = False,
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Modify one record of a table"""
    record = dict(record) # type: ignore
    try:
        record['id'] = int(record['id']) # type: ignore
    except ValueError:
        raise typer.BadParameter('Record ID must be a number')
    st, res = grist_api.update_records(table, [record], noparse, doc_id, team_id) # type: ignore
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

# Note: again, we don't cover add_update_records because it is too 
# sophisticated for our very limited way of describing a record in the cli

@rec_app.command('delete')
def delete_records(
    records: Annotated[List[int], typer.Argument(
                       help='ID of the records to delete')],
    table: Annotated[str, _table_id_opt],
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Delete records from a table"""
    st, res = grist_api.delete_rows(table, records, doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

# gry att -> for managing attachments
# ----------------------------------------------------------------------
@att_app.command('list')
def list_atts(sort: Annotated[str, _sort_opt] = '',
              limit: Annotated[int, _limit_opt] = 0,
              doc_id: Annotated[str, _doc_id_opt] = '', 
              team_id: Annotated[str, _team_id_opt] = '',
              quiet: Annotated[bool, _quiet_opt] = False,
              verbose: Annotated[int, _verbose_opt] = 0,
              inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """List metadata of attachments in a doc. No filter option available"""
    st, res = grist_api.list_attachments(sort=sort, limit=limit, doc_id=doc_id, 
                                         team_id=team_id)
    if not _exit_early(st, res, quiet, verbose, inspect):
        content = Table('att. id', 'metadata')
        for c in res:
            f = c['fields']
            mdata = '\n'.join([f'{k}: {str(v)}' for k, v in f.items()])
            content.add_row(str(c['id']), mdata)
            content.add_section()
        cli_console.print(content)

@att_app.command('see')
def see_attachment(att_id: Annotated[int, typer.Argument(help='The attachment ID')],
                   doc_id: Annotated[str, _doc_id_opt] = '', 
                   team_id: Annotated[str, _team_id_opt] = '',
                   quiet: Annotated[bool, _quiet_opt] = False,
                   verbose: Annotated[int, _verbose_opt] = 0,
                   inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Get the metadata for an attachment"""
    st, res = grist_api.see_attachment(att_id, doc_id, team_id)
    if not _exit_early(st, res, quiet, verbose, inspect):
        content = Table('key', 'value')
        content.add_row('ID', str(att_id))
        for k, v in res.items():
            content.add_row(k, str(v))
        cli_console.print(content)

@att_app.command('download')
def download_att(
    filename: Annotated[Path, typer.Argument(help='Output file path', 
                        callback=_download_path_validate)],
    attachment: Annotated[int, typer.Option('--attachment', '-a',
                          help='The attachment ID', 
                          prompt='Insert the attachment ID')],
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Download one attachment as a file"""
    st, res = grist_api.download_attachment(filename, attachment, 
                                            doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)
    
@att_app.command('upload')
def upload_atts(
    filenames: Annotated[List[Path], typer.Argument(help='Files to upload', 
                         callback=_upload_pathlist_validate)],
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Upload one or more attachments to a doc"""
    st, res = grist_api.upload_attachments(filenames, doc_id, team_id)
    _exit_early_or_print_id(st, res, quiet, verbose, inspect)

class _DownloadAttOption(str, Enum):
    tar = 'tar'
    zip = 'zip'

@att_app.command('backup')
def download_atts(
    filename: Annotated[Path, typer.Argument(help='Output file path', 
                        callback=_download_path_validate)],
    output: Annotated[_DownloadAttOption, _outmode_opt] = _DownloadAttOption.tar,
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Download all attachments as an archive file"""
    st, res = grist_api.download_attachments(filename, output, doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@att_app.command('restore')
def upload_restore_atts(
    filename: Annotated[Path, typer.Argument(help='Archive file path', 
                        callback=_upload_path_validate)],
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Upload missing attachments from a local tar archive"""
    st, res = grist_api.upload_restore_attachments(filename, doc_id, team_id)
    _exit_early_or_print_content(st, res, quiet, verbose, inspect)

@att_app.command('purge')
def purge_atts(
    old: Annotated[bool, typer.Option('--only-old', 
                   help='Only if unused for a long time')] = False,  
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Delete unused attachments from the document"""
    st, res = grist_api.delete_unused_attachments(old, doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@att_app.command('store')
def see_att_store(doc_id: Annotated[str, _doc_id_opt] = '', 
                  team_id: Annotated[str, _team_id_opt] = '',
                  quiet: Annotated[bool, _quiet_opt] = False,
                  verbose: Annotated[int, _verbose_opt] = 0,
                  inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Get the attachments storage type"""
    st, res = grist_api.see_attachment_store(doc_id, team_id)
    _exit_early_or_print_content(st, res, quiet, verbose, inspect)

@att_app.command('set-store')
def change_att_store(
    internal: Annotated[bool, typer.Option('--internal/--external', '-i/-e', 
                        help='The storage type')] = True,
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Set the attachments storage type"""
    st, res = grist_api.update_attachment_store(internal, doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@att_app.command('store-settings')
def list_store_settings(doc_id: Annotated[str, _doc_id_opt] = '', 
                        team_id: Annotated[str, _team_id_opt] = '',
                        quiet: Annotated[bool, _quiet_opt] = False,
                        verbose: Annotated[int, _verbose_opt] = 0,
                        inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Get the attachments storage settings"""
    st, res = grist_api.list_store_settings(doc_id, team_id)
    _exit_early_or_print_content(st, res, quiet, verbose, inspect)

@att_app.command('transfer')
def transfer_atts(doc_id: Annotated[str, _doc_id_opt] = '', 
                  team_id: Annotated[str, _team_id_opt] = '',
                  quiet: Annotated[bool, _quiet_opt] = False,
                  verbose: Annotated[int, _verbose_opt] = 0,
                  inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Start transferring attachments"""
    st, res = grist_api.transfer_attachments(doc_id, team_id)
    _exit_early_or_print_content(st, res, quiet, verbose, inspect)

@att_app.command('transfer-status')
def transfer_status(doc_id: Annotated[str, _doc_id_opt] = '', 
                    team_id: Annotated[str, _team_id_opt] = '',
                    quiet: Annotated[bool, _quiet_opt] = False,
                    verbose: Annotated[int, _verbose_opt] = 0,
                    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Get attachment transfer status"""
    st, res = grist_api.see_transfer_status(doc_id, team_id)
    _exit_early_or_print_content(st, res, quiet, verbose, inspect)

# gry hook -> for managing webhooks
# ----------------------------------------------------------------------
@hook_app.command('list')
def list_hooks(doc_id: Annotated[str, _doc_id_opt] = '', 
               team_id: Annotated[str, _team_id_opt] = '',
               quiet: Annotated[bool, _quiet_opt] = False,
               verbose: Annotated[int, _verbose_opt] = 0,
               inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """List webhooks associated with a document"""
    st, res = grist_api.list_webhooks(doc_id, team_id)
    if not _exit_early(st, res, quiet, verbose, inspect):
        if not res:
            content = 'No webhooks.'
        else:
            content = Table('webhook data')
            for wh in res:
                data = f'id: {wh["id"]}\n'
                data += f'name: {wh["fields"]["name"]}\n'
                data += f'url: {wh["fields"]["url"]}\n'
                data += f'enabled: {wh["fields"]["enabled"]}\n'
                data += f'table: {wh["fields"]["tableId"]}\n'
                data += f'events: {", ".join(wh["fields"]["eventTypes"])}'
                content.add_row(data)
                content.add_section()
        cli_console.print(content)

@hook_app.command('new')
def add_hook(
    name: Annotated[str, typer.Argument(help='Webhook name')],
    url: Annotated[str, typer.Argument(help='Webhook url')],
    table: Annotated[str, _table_id_opt],
    events: Annotated[str, typer.Option('--events',  
                      help='Event types :-separated, eg "add:update"')] = 'add',
    readycol: Annotated[str|None, typer.Option('--ready',  
                        help='Is Ready Columm (str or null)')] = None,
    enabled: Annotated[bool, typer.Option('--enabled/--disabled',  
                       help='Webhook is enabled')] = True,
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Add one webhook to a document"""
    evts = events.split(':')
    wh = {'fields': {'name': name, 'memo': '', 'url': url, 'enabled': enabled, 
          'eventTypes': evts, 'isReadyColumn': readycol, 'tableId': table}}
    st, res = grist_api.add_webhooks([wh], doc_id, team_id)
    if not _exit_early(st, res, quiet, verbose, inspect):
        cli_console.print(f'{DONEMSG} Id: {res[0]}')

@hook_app.command('update')
def update_hook(
    hook_id: Annotated[str, typer.Argument(help='The webhook ID')],
    name: Annotated[str, typer.Option('--name', help='Webhook name')] = '<same>',
    url: Annotated[str, typer.Option('--url', help='Webhook url')] = '<same>',
    table: Annotated[str, typer.Option('--table', help='Table ID name')] = '<same>',
    events: Annotated[str, typer.Option('--events', 
                      help='Event types :-separated, eg "add:update"')] = '<same>',
    readycol: Annotated[str|None, typer.Option('--ready',
                        help='Is Ready Columm (str or null)')] = '<same>',
    enabled: Annotated[bool|None, typer.Option('--enabled/--disabled',  
                       help='Webhook is enabled')] = None,
    doc_id: Annotated[str, _doc_id_opt] = '', 
    team_id: Annotated[str, _team_id_opt] = '',
    quiet: Annotated[bool, _quiet_opt] = False,
    verbose: Annotated[int, _verbose_opt] = 0,
    inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Modify a webhook"""
    fields = dict()
    for option, label in ((name, 'name'), (url, 'url'), (table, 'tableId'),
                          (readycol, 'isReadyColumn')):
        if option != '<same>':
            fields[label] = option
    if enabled is not None:
        fields['enabled'] = enabled
    if events != '<same>':
        evts = events.split(':')
        fields['eventTypes'] = evts
    wh = {'fields': fields}
    st, res = grist_api.update_webhook(hook_id, wh, doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@hook_app.command('delete')
def delete_hook(hook_id: Annotated[str, typer.Argument(help='The webhook ID')],
                doc_id: Annotated[str, _doc_id_opt] = '', 
                team_id: Annotated[str, _team_id_opt] = '',
                quiet: Annotated[bool, _quiet_opt] = False,
                verbose: Annotated[int, _verbose_opt] = 0,
                inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Delete a webhook"""
    st, res = grist_api.delete_webhook(hook_id, doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)

@hook_app.command('empty-queue')
def empty_hook_queue(doc_id: Annotated[str, _doc_id_opt] = '', 
                     team_id: Annotated[str, _team_id_opt] = '',
                     quiet: Annotated[bool, _quiet_opt] = False,
                     verbose: Annotated[int, _verbose_opt] = 0,
                     inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Empty a document's queue of undelivered payloads"""
    st, res = grist_api.empty_payloads_queue(doc_id, team_id)
    _exit_early_or_print_done(st, res, quiet, verbose, inspect)


if __name__ == '__main__':
    app()
