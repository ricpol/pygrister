# this is a first draft for a Pygrister cli. 


#TODO exit codes for the cli:
# 0 -> ok
# 1 -> error on our side (Python/Requests/Pygrister exception raised), 
#      managed by Typer (ie, nicely formatted stacktrace)
# 2 -> unclear but I *think* it's used by Click/Typer for usage errors, 
#      ie errors in cli invocation, see click/exceptions.py
# 3 -> we reserve this for errors on api call side (eg http 404)

import os, os.path
import json as modjson
from pathlib import Path
from enum import Enum
from typing import List, Optional
from typing_extensions import Annotated

import typer
from rich.console import Console
from rich.table import Table

from pygrister.api import GristApi
from pygrister.config import Configurator, PYGRISTER_CONFIG
try:
    from cliconverters import cli_out_converters # type: ignore
except (ModuleNotFoundError, ImportError):
    cli_out_converters = dict()
try:
    from cliconverters import cli_in_converters # type: ignore
except (ModuleNotFoundError, ImportError):
    cli_in_converters = dict()

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
        pth = os.path.join(os.path.expanduser('~'), '.gristapi/config.json')
        if os.path.isfile(pth):
            with open(pth, 'r') as f:
                config.update(modjson.loads(f.read()))
        if os.path.isfile('gryconf.json'): 
            with open('gryconf.json', 'r', encoding='utf8') as f:
                config.update(modjson.loads(f.read()))
        for k in config.keys():
            try:
                config[k] = os.environ[k]
            except KeyError:
                pass
        # overrides
        config['GRIST_RAISE_ERROR'] = 'N'
        config['GRIST_SAFEMODE'] = 'N'
        # GristApi will happily crash with a ValueError when ws_id (an int!) 
        # is needed but left unspecified (eg, the default str(!) in the 
        # static config). As a fix, we replace the default with '0': still 
        # an invalid id, but a number, so it won't crash and return http404
        try:
            int(config['GRIST_WORKSPACE_ID'])
        except ValueError:
            config['GRIST_WORKSPACE_ID'] = '0'
        return config

    def update_config(self, config: dict[str, str]):
        # since this is a one-off configurator for cli calls only, 
        # updating config at runtime is not supported
        raise NotImplementedError

# the global GristApi (re-creadted at every cli call): inside a cli function, 
# all api calls (usually just one but may be more) will use this instance
_c = _CliConfigurator()
grist_api = GristApi(custom_configurator=_c)
grist_api.in_converter = cli_in_converters
grist_api.out_converter = cli_out_converters
# the global Rich console where everything should be printed
cli_console = Console()

BADCALL = 3 # the exit code we reserve for bad call errors (eg http 404)
DONEMSG = '[green]Done.[/green]'
ERRMSG = '[bold red]Error![/bold red]'

# a few helper functions
# ----------------------------------------------------------------------
def _exit_with_error(st, res, inspect) -> None:
    if inspect:
        cli_console.print(grist_api.inspect())
        cli_console.rule()
    cli_console.print(ERRMSG, 'Status:', st, res)
    raise typer.Exit(BADCALL)

def _exit_if_error(st, res, inspect) -> None:
    # no need to differenciate by verbosity if st>=300 
    # because Pygrister already reports the api response as it is
    if not grist_api.ok:
        if inspect:
            cli_console.print(grist_api.inspect())
            cli_console.rule()
        cli_console.print(ERRMSG, 'Status:', st, res)
        raise typer.Exit(BADCALL)

def _print_done_or_exit(st, res, verbose, inspect) -> None:
    if inspect:
        cli_console.print(grist_api.inspect())
        cli_console.rule()
    if grist_api.ok: 
        if verbose == 0:
            cli_console.print(DONEMSG)
        elif verbose == 1:
            cli_console.print(res)
        else:
            cli_console.print(grist_api.resp_content)
    else:
        cli_console.print(ERRMSG, 'Status:', st, res)
        raise typer.Exit(BADCALL)

def _print_output(content, res, verbose, inspect) -> None:
    if inspect:
        cli_console.print(grist_api.inspect())
        cli_console.rule()
    # we print different things, depending on verbose level
    # note that we always have the cli output ready, even if we won't use it
    if verbose == 0: # the nicely formatted cli output (text)
        cli_console.print(content)
    elif verbose == 1: # the response from Pygrister (Python object)
        cli_console.print(res)
    else: # the original Grist api response (json)
        cli_console.print(grist_api.resp_content)

def _print_done_and_id(content, res, verbose, inspect) -> None:
    if inspect:
        cli_console.print(grist_api.inspect())
        cli_console.rule()
    if verbose == 0:
        cli_console.print(DONEMSG, 'Id:', content)
    elif verbose == 1:
        cli_console.print(res)
    else:
        cli_console.print(grist_api.resp_content)

def _make_user_table(response) -> Table:
    table = Table('id', 'name', 'email', 'access')
    for usr in response:
        table.add_row(str(usr['id']), usr['name'], usr['email'], 
                      str(usr['access']))
    return table

def _user_access_validate(value):
    legal = 'owners editors viewers members none'
    if value not in legal.split():
        raise typer.BadParameter(f'Access must be one of: {legal}')
    if value == 'none':
        value = None
    return value

def _user_max_access_validate(value):
    legal = 'owners editors viewers'
    if value not in legal.split():
        raise typer.BadParameter(f'Access must be one of: {legal}')
    if value == 'none':
        value = None
    return value

def _column_decl_validate(value):
    res = []
    for item in value:
        try:
            id_, type_, name = item.split(':')
        except ValueError:
            raise typer.BadParameter('Column must be declared as "id:type:label"')
        res.append([id_, type_, name])
    return res

def _variadic_options_validate(value):
    try:
        return dict(zip(*[iter([i.strip('--') for i in value])]*2, strict=True))
    except ValueError:
        raise typer.BadParameter('Improper use of extra option(s)')


# a few recurrent Typer options
# ----------------------------------------------------------------------
_verbose_opt = typer.Option('--verbose', '-v', count=True,
                            help='Verbose level (0-2)')
_inspect_opt = typer.Option('--inspect', '-i', 
                            help = 'Print inspect output after api call')
_team_id_opt = typer.Option('--team', '-m', 
                            help='The team ID [default: current]')
_ws_id_opt = typer.Option('--workspace', '-w', 
                          help='The workspace integer ID [default: current]')
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

# Typer sub-commands
# ----------------------------------------------------------------------
org_app = typer.Typer(help='Manage Grist teams (aka organisations)')
ws_app = typer.Typer(help='Manage workspaces inside a team site')
doc_app = typer.Typer(help='Manage documents inside a workspace')
table_app = typer.Typer(help='Manage a table inside a document')
app = typer.Typer(no_args_is_help=True)
app.add_typer(org_app, name='team', no_args_is_help=True)
app.add_typer(ws_app, name='ws', no_args_is_help=True)
app.add_typer(doc_app, name='doc', no_args_is_help=True)
app.add_typer(table_app, name='table', no_args_is_help=True)

# gry sql -> post SELECT sql queries to Grist
# ----------------------------------------------------------------------

@app.command('sql')
def run_sql(statement: Annotated[str, typer.Argument(
                                help='The sql statement - SELECT only')],
            params: Annotated[Optional[List[str]], typer.Option('--param', '-p',
                                help='Query parameters')] = None,
            timeout: Annotated[int, typer.Option('--timeout', '-t', 
                                help='Query timeout')] = 1000,
            doc_id: Annotated[str, _doc_id_opt] = '', 
            team_id: Annotated[str, _team_id_opt] = '',
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
    _exit_if_error(st, res, inspect)
    if res:
        content = Table(*res[0].keys())
        for row in res:
            content.add_row(*[str(v) for v in row.values()])
    else:
        content = 'No records found.'
    _print_output(content, res, verbose, inspect)

# gry team -> for managing team sites (organisations)
# ----------------------------------------------------------------------
@org_app.command('list')
def list_orgs(verbose: Annotated[int, _verbose_opt] = 0,
              inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """List the teams you have access to"""
    st, res = grist_api.list_team_sites()
    _exit_if_error(st, res, inspect)
    content = Table('id', 'name', 'owner')
    for org in res:
        content.add_row(str(org['id']), org['name'], org['owner']['name'])
    _print_output(content, res, verbose, inspect)

@org_app.command('see')
def see_org(team_id: Annotated[str, _team_id_opt] = '', 
            verbose: Annotated[int, _verbose_opt] = 0,
            inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Describe a team"""
    st, res = grist_api.see_team(team_id)
    _exit_if_error(st, res, inspect) 
    content = Table('key', 'value')
    content.add_row('id', str(res['id']))
    content.add_row('name', res['name'])
    content.add_row('domain', res['domain'])
    content.add_row('owner', f"{res['owner']['id']} - {res['owner']['name']}")
    _print_output(content, res, verbose, inspect)

@org_app.command('update')
def update_org(name: Annotated[str, typer.Argument(help='The new name')], 
               team_id: Annotated[str, _team_id_opt] = '',
               verbose: Annotated[int, _verbose_opt] = 0,
               inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Change the team name"""
    st, res = grist_api.update_team(name, team_id)
    _print_done_or_exit(st, res, verbose, inspect)
     
@org_app.command('delete')
def delete_org(team_id: Annotated[str, _team_id_opt] = '',
               verbose: Annotated[int, _verbose_opt] = 0,
               inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Delete a team"""
    st, res = grist_api.delete_team(team_id)
    _print_done_or_exit(st, res, verbose, inspect)

@org_app.command('users')
def list_org_users(team_id: Annotated[str, _team_id_opt] = '',  
                   verbose: Annotated[int, _verbose_opt] = 0,
                   inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """List users with access to team"""
    st, res = grist_api.list_team_users(team_id)
    _exit_if_error(st, res, inspect)
    content = _make_user_table(res)
    _print_output(content, res, verbose, inspect)

@org_app.command('user-access')
def change_team_access(uid: Annotated[int, typer.Argument(help='The user ID')], 
                       access: Annotated[str, _access_opt],
                       team_id: Annotated[str, _team_id_opt] = '',
                       verbose: Annotated[int, _verbose_opt] = 0,
                       inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Change user access level to a team"""
    st, res = grist_api.list_team_users(team_id)
    _exit_if_error(st, res, inspect)
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
    _print_done_or_exit(st, res, verbose, inspect)
        
#TODO "change_user_access" is only for existing users, but "update_team_users"
# allows for adding users too. Maybe add a separate cli endpoint for this?

# gry ws -> for managing workspaces
# ----------------------------------------------------------------------
@ws_app.command('list')
def list_ws(team_id: Annotated[str, _team_id_opt] = '', 
            verbose: Annotated[int, _verbose_opt] = 0,
            inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """List workspaces and documents in a team"""
    st, res = grist_api.list_workspaces(team_id)
    _exit_if_error(st, res, inspect)
    content = Table('id', 'name', 'owner', 'email', 'docs')
    for ws in res:
        numdocs = len(ws.get('docs', []))
        content.add_row(str(ws['id']), ws['name'], str(ws['owner']['id']), 
                        ws['owner']['email'], str(numdocs))
    _print_output(content, res, verbose, inspect)

@ws_app.command('new')
def add_ws(name: Annotated[str, typer.Argument(help='The name of new ws')], 
           team_id: Annotated[str, _team_id_opt] = '',
           verbose: Annotated[int, _verbose_opt] = 0,
           inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Create an empty workspace"""
    st, res = grist_api.add_workspace(name, team_id)
    _exit_if_error(st, res, inspect)
    _print_done_and_id(res, res, verbose, inspect)

@ws_app.command('see')
def see_ws(ws_id: Annotated[int, _ws_id_opt] = 0,
           verbose: Annotated[int, _verbose_opt] = 0,
           inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Describe a workspace"""
    st, res = grist_api.see_workspace(ws_id)
    _exit_if_error(st, res, inspect)
    content = Table('key', 'value')
    content.add_row('id', str(res['id']))
    content.add_row('name', res['name'])
    content.add_row('team', f"{res['org']['id']} - {res['org']['name']}")
    content.add_section()
    for doc in res.get('docs', []):
        content.add_row('doc', f"{doc['id']} - {doc['name']}")
    _print_output(content, res, verbose, inspect)

@ws_app.command('update')
def update_ws(name: Annotated[str, typer.Argument(help='The new name')], 
              ws_id: Annotated[int, _ws_id_opt] = 0,
              verbose: Annotated[int, _verbose_opt] = 0,
              inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Change the workspace name"""
    st, res = grist_api.update_workspace(name, ws_id)
    _print_done_or_exit(st, res, verbose, inspect)

@ws_app.command('delete')
def delete_ws(ws_id: Annotated[int, _ws_id_opt] = 0,
              verbose: Annotated[int, _verbose_opt] = 0,
              inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Delete a workspace"""
    st, res = grist_api.delete_workspace(ws_id)
    _print_done_or_exit(st, res, verbose, inspect)

@ws_app.command('users')
def list_ws_users(ws_id: Annotated[int, _ws_id_opt] = 0,  
                  verbose: Annotated[int, _verbose_opt] = 0,
                  inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """List users with access to workspace"""
    st, res = grist_api.list_workspace_users(ws_id)
    _exit_if_error(st, res, inspect)
    content = _make_user_table(res)
    _print_output(content, res, verbose, inspect)

@ws_app.command('user-access')
def change_ws_access(uid: Annotated[int, typer.Argument(help='The user ID')], 
                     access: Annotated[str, _access_opt],
                     ws_id: Annotated[int, _ws_id_opt] = 0,
                     verbose: Annotated[int, _verbose_opt] = 0,
                     inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Change user access level to a workspace"""
    st, res = grist_api.list_workspace_users(ws_id)
    _exit_if_error(st, res, inspect)
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
    _print_done_or_exit(st, res, verbose, inspect)
        
#TODO "change_ws_access" is only for existing users, but "update_team_users"
# allows for adding users too. Maybe add a separate cli endpoint for this?

# gry doc -> for managing documents
# ----------------------------------------------------------------------

_pinned_opt = typer.Option('--pinned/--no-pinned', '-P/-p', help='Is pinned')

@doc_app.command('new')
def add_doc(name: Annotated[str, typer.Argument(help='The name of new doc')], 
            pinned: Annotated[bool, _pinned_opt] = False,
            ws_id: Annotated[int, _ws_id_opt] = 0, 
            verbose: Annotated[int, _verbose_opt] = 0,
            inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Create an empty document"""
    st, res = grist_api.add_doc(name, pinned, ws_id)
    _exit_if_error(st, res, inspect)
    _print_done_and_id(res, res, verbose, inspect)

@doc_app.command('see')
def see_doc(doc_id: Annotated[str, _doc_id_opt] = '', 
            team_id: Annotated[str, _team_id_opt] = '',
            verbose: Annotated[int, _verbose_opt] = 0,
            inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Describe a document"""
    st, res = grist_api.see_doc(doc_id, team_id)
    _exit_if_error(st, res, inspect)
    content = Table('key', 'value')
    content.add_row('id', res['id'])
    content.add_row('name', res['name'])
    content.add_row('pinned', str(res['isPinned']))
    content.add_row('workspace', 
        f"{res['workspace']['id']} - {res['workspace']['name']}")
    content.add_row('team', 
        f"{res['workspace']['org']['id']} - {res['workspace']['org']['name']}")
    _print_output(content, res, verbose, inspect)

@doc_app.command('update')
def update_doc(name: Annotated[str, typer.Argument(help='The new name')],
               pinned: Annotated[bool, _pinned_opt] = False,
               doc_id: Annotated[str, _doc_id_opt] = '', 
               team_id: Annotated[str, _team_id_opt] = '',
               verbose: Annotated[int, _verbose_opt] = 0,
               inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Modify document metadata"""
    st, res = grist_api.update_doc(name, pinned, doc_id, team_id)
    _print_done_or_exit(st, res, verbose, inspect)

@ doc_app.command('move')
def move_doc(dest: Annotated[int, typer.Argument( 
                             help='Destination ws integer ID')],
             doc_id: Annotated[str, _doc_id_opt] = '', 
             team_id: Annotated[str, _team_id_opt] = '',
             verbose: Annotated[int, _verbose_opt] = 0,
             inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Move document to another workspace"""
    st, res = grist_api.move_doc(dest, doc_id, team_id)
    _print_done_or_exit(st, res, verbose, inspect)

@doc_app.command('delete')
def delete_doc(doc_id: Annotated[str, _doc_id_opt] = '', 
               team_id: Annotated[str, _team_id_opt] = '',
               verbose: Annotated[int, _verbose_opt] = 0,
               inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Delete a document"""
    st, res = grist_api.delete_doc(doc_id, team_id)
    _print_done_or_exit(st, res, verbose, inspect)

@doc_app.command('purge-history')
def delete_doc_history(keep: Annotated[int, typer.Option('--keep', '-k', 
                                       help='Latest actions to keep')] = 0,
                       doc_id: Annotated[str, _doc_id_opt] = '', 
                       team_id: Annotated[str, _team_id_opt] = '',
                       verbose: Annotated[int, _verbose_opt] = 0,
                       inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Delete the document action history"""
    st, res = grist_api.delete_doc_history(keep, doc_id, team_id)
    _print_done_or_exit(st, res, verbose, inspect)

@doc_app.command('reload')
def reload_doc(doc_id: Annotated[str, _doc_id_opt] = '', 
               team_id: Annotated[str, _team_id_opt] = '',
               verbose: Annotated[int, _verbose_opt] = 0,
               inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Reload a document"""
    st, res = grist_api.reload_doc(doc_id, team_id)
    _print_done_or_exit(st, res, verbose, inspect)

@doc_app.command('users')
def list_doc_users(doc_id: Annotated[str, _doc_id_opt] = '', 
                   team_id: Annotated[str, _team_id_opt] = '',
                   verbose: Annotated[int, _verbose_opt] = 0,
                   inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """List users with access to document"""
    st, res = grist_api.list_doc_users(doc_id, team_id)
    _exit_if_error(st, res, inspect)
    content = _make_user_table(res)
    _print_output(content, res, verbose, inspect)

@doc_app.command('user-access')
def change_doc_access(uid: Annotated[int, typer.Argument(help='The user ID')], 
                      access: Annotated[str, _access_opt],
                      max_access: Annotated[str, _max_access_opt] = 'owners', 
                      doc_id: Annotated[str, _doc_id_opt] = '', 
                      team_id: Annotated[str, _team_id_opt] = '',
                      verbose: Annotated[int, _verbose_opt] = 0,
                      inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Change user access level to a document"""
    st, res = grist_api.list_doc_users(doc_id, team_id)
    _exit_if_error(st, res, inspect)
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
    _print_done_or_exit(st, res, verbose, inspect)

#TODO again, this is for existing users only, but the api 
# allows for adding users too. Maybe add a separate cli endpoint for this?
 
@doc_app.command('download')
def download_db(filename: Annotated[Path, typer.Argument(help='Output file path')],
                history: Annotated[bool, 
                    typer.Option('--history/--no-history', '-H/-h', 
                                 help='Include history')] = False, 
                template: Annotated[bool, 
                    typer.Option('--template/--no-template', '-P/-p', 
                                 help='Template only, no data')] = False, 
                doc_id: Annotated[str, _doc_id_opt] = '', 
                team_id: Annotated[str, _team_id_opt] = '',
                inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Download the document as sqlite file"""
    nohistory = not history
    st, res = grist_api.download_sqlite(str(filename), nohistory, template, 
                                        doc_id, team_id)
    _print_done_or_exit(st, res, 0, inspect) # force verbose=0 in download mode


# gry table -> for managing tables
# ----------------------------------------------------------------------

@table_app.command('list')
def list_tables(doc_id: Annotated[str, _doc_id_opt] = '', 
                team_id: Annotated[str, _team_id_opt] = '',
                verbose: Annotated[int, _verbose_opt] = 0,
                inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """List tables in a document"""
    st, res = grist_api.list_tables(doc_id, team_id)
    _exit_if_error(st, res, inspect)
    content = Table('table id', 'metadata')
    for t in res:
        f = t['fields']
        mdata = '\n'.join([f'{k}: {v}' for k, v in f.items()])
        content.add_row(t['id'], mdata)
        content.add_section()
    _print_output(content, res, verbose, inspect)

@table_app.command('new')
def new_table(cols: Annotated[List[str], typer.Argument(
                        callback=_column_decl_validate,
                        help='Column list, each declared as "id:type:label"')],
              tname: Annotated[str, _table_id_opt], 
              doc_id: Annotated[str, _doc_id_opt] = '', 
              team_id: Annotated[str, _team_id_opt] = '',
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
    _exit_if_error(st, res, inspect)
    _print_done_and_id(res[0], res, verbose, inspect)

@table_app.command('update', context_settings={'allow_extra_args': True, 
                                               'ignore_unknown_options': True})
def update_table(ctx: typer.Context,
                 tname: Annotated[str, _table_id_opt], 
                 doc_id: Annotated[str, _doc_id_opt] = '', 
                 team_id: Annotated[str, _team_id_opt] = '',
                 verbose: Annotated[int, _verbose_opt] = 0,
                 inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Update table metadata.
    
    Pass any metadata field as an extra option, eg: 
    
    % gry table update -n Mytable --tableRef 2 --onDemand false"""
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
    _print_done_or_exit(st, res, verbose, inspect)

class _DownloadOption(str, Enum):
    excel = 'excel'
    csv = 'csv'
    schema = 'schema'

class _HeaderOption(str, Enum):
    label = 'label'
    colid = 'colId'

@table_app.command('download')
def download_table(
        filename: Annotated[Path, typer.Argument(help='Output file path')],
        tname: Annotated[str, _table_id_opt], 
        output: Annotated[_DownloadOption, typer.Option('--output', '-o', 
                                help='Output type')] = _DownloadOption.csv,
        header: Annotated[_HeaderOption, typer.Option('--header', '-h', 
                                help='Column headers')] = _HeaderOption.label,
        doc_id: Annotated[str, _doc_id_opt] = '', 
        team_id: Annotated[str, _team_id_opt] = '',
        inspect: Annotated[bool, _inspect_opt] = False) -> None:
    """Dumps the content or the schema of a table to FILENAME"""
    funcs = {_DownloadOption.csv: grist_api.download_csv, 
             _DownloadOption.excel: grist_api.download_excel,
             _DownloadOption.schema: grist_api.download_excel}
    st, res = funcs[output](str(filename), tname, header, doc_id, team_id)
    _print_done_or_exit(st, res, 0, inspect) # force verbose=0 in download mode



if __name__ == '__main__':
    app()
