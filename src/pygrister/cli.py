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
from typing_extensions import Annotated

import typer
from rich.console import Console
from rich.table import Table

from pygrister.api import GristApi
from pygrister.config import Configurator, PYGRISTER_CONFIG


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
        return config

    def update_config(self, config: dict[str, str]):
        # since this is a one-off configurator for cli calls only, 
        # updating config at runtime is not supported
        raise NotImplementedError

# the global GristApi (re-creadted at every cli call): inside a cli function, 
# all api calls (usually just one but may be more) will use this instance
_c = _CliConfigurator()
the_grist = GristApi(custom_configurator=_c)
# the global Rich console where everyone should be printed
cli_console = Console()

BADCALL = 3 # the exit code we reserve for bad call errors (eg http 404)
DONEMSG = '[green]Done.[/green]'
ERRMSG = '[bold red]Error![/bold red]'

# a few helper functions
# ----------------------------------------------------------------------
def _exit_with_error(st, res, inspect) -> None:
    if inspect:
        cli_console.print(the_grist.inspect())
        cli_console.rule()
    cli_console.print(ERRMSG, 'Status:', st, res)
    raise typer.Exit(BADCALL)

def _exit_if_error(st, res, inspect) -> None:
    if not the_grist.ok:
        if inspect:
            cli_console.print(the_grist.inspect())
            cli_console.rule()
        cli_console.print(ERRMSG, 'Status:', st, res)
        raise typer.Exit(BADCALL)

def _print_done_or_exit(st, res, inspect) -> None:
    if inspect:
        cli_console.print(the_grist.inspect())
        cli_console.rule()
    if the_grist.ok: 
        cli_console.print(DONEMSG)
    else:
        cli_console.print(ERRMSG, 'Status:', st, res)
        raise typer.Exit(BADCALL)

def _print_content(content, inspect) -> None:
    if inspect:
        cli_console.print(the_grist.inspect())
        cli_console.rule()
    cli_console.print(content)

def _make_user_table(response) -> None:
    table = Table('id', 'name', 'email', 'access')
    for usr in response:
        table.add_row(str(usr['id']), usr['name'], usr['email'], 
                      str(usr['access']))
    cli_console.print(table)

def _user_access_validate(value):
    legal = 'owners editors viewers members none'
    if value not in legal.split():
        raise typer.BadParameter(f'Access must be one of: {legal}')
    if value == 'none':
        value = None
    return value

# a few recurrent Typer options
# ----------------------------------------------------------------------
details_opt = typer.Option('--details/--no-details', '-D/-d',
                           help='Long/short info')
inspect_opt = typer.Option('--inspect', '-i', 
                           help = 'Print inspect output after api call')
team_id_opt = typer.Option('--team', '-t', 
                           help='The team ID [default: current]')
ws_id_opt = typer.Option('--workspace', '-w', 
                         help='The workspace ID [default: current]')
access_opt = typer.Option('--access', '-a', 
                          help='The new access level',
                          callback=_user_access_validate)

# Typer sub-commands
# ----------------------------------------------------------------------
org_app = typer.Typer(help='Manage Grist teams (aka organisations)')
ws_app = typer.Typer(help='Manage workspaces inside a team site')
app = typer.Typer(no_args_is_help=True)
app.add_typer(org_app, name='team', no_args_is_help=True)
app.add_typer(ws_app, name='ws', no_args_is_help=True)


# gry team -> for managing team sites (organisations)
# ----------------------------------------------------------------------
@org_app.command('list')
def list_orgs(inspect: Annotated[bool, inspect_opt] = False) -> None:
    """List the teams you have access to"""
    st, res = the_grist.list_team_sites()
    _exit_if_error(st, res, inspect)
    table = Table('id', 'name', 'owner')
    for org in res:
        table.add_row(str(org['id']), org['name'], org['owner']['name'])
    _print_content(table, inspect)

@org_app.command('see')
def see_org(team_id: Annotated[str, team_id_opt] = '', 
            details: Annotated[bool, details_opt] = False,
            inspect: Annotated[bool, inspect_opt] = False) -> None:
    """Describe a team"""
    st, res = the_grist.see_team(team_id)
    _exit_if_error(st, res, inspect) 
    if details:
        content = res
    else:
        table = Table('key', 'value')
        table.add_row('id', str(res['id']))
        table.add_row('name', res['name'])
        table.add_row('domain', res['domain'])
        table.add_row('owner', f"{res['owner']['id']} - {res['owner']['name']}")
        content = table
    _print_content(content, inspect)

@org_app.command('update')
def update_org(name: Annotated[str, typer.Argument(help='The new name')], 
               team_id: Annotated[str, team_id_opt] = '',
               inspect: Annotated[bool, inspect_opt] = False) -> None:
    """Change the team name"""
    st, res = the_grist.update_team(name, team_id)
    _print_done_or_exit(st, res, inspect)
     
@org_app.command('delete')
def delete_org(team_id: Annotated[str, team_id_opt] = '',
               inspect: Annotated[bool, inspect_opt] = False) -> None:
    """Delete a team"""
    st, res = the_grist.delete_team(team_id)
    _print_done_or_exit(st, res, inspect)

@org_app.command('users')
def list_org_users(team_id: Annotated[str, team_id_opt] = '',  
                   details: Annotated[bool, details_opt] = False,
                   inspect: Annotated[bool, inspect_opt] = False) -> None:
    """List users with access to team"""
    st, res = the_grist.list_team_users(team_id)
    _exit_if_error(st, res, inspect)
    content = res if details else _make_user_table(res)
    _print_content(content, inspect)

@org_app.command('user-access')
def change_team_access(uid: Annotated[int, typer.Argument(help='The user ID')], 
                       access: Annotated[str, access_opt],
                       team_id: Annotated[str, team_id_opt] = '',
                       inspect: Annotated[bool, inspect_opt] = False) -> None:
    """Change user access level to a team"""
    st, res = the_grist.list_team_users(team_id)
    _exit_if_error(st, res, inspect)
    usr_email = ''
    for usr in res:
        if usr['id'] == uid:
            usr_email = usr['email']
            break
    if not usr_email:
        if inspect:
            cli_console.print(the_grist.inspect())
            cli_console.rule()
        raise typer.BadParameter('User id not found.')
    users = {usr_email: access}
    st, res = the_grist.update_team_users(users, team_id)
    _print_done_or_exit(st, res, inspect)
        
#TODO "change_user_access" is only for existing users, but "update_team_users"
# allows for adding users too. Maybe add a separate cli endpoint for this?

# gry ws -> for managing workspaces
# ----------------------------------------------------------------------
@ws_app.command('list')
def list_ws(team_id: Annotated[str, team_id_opt] = '', 
            details: Annotated[bool, details_opt] = False,
            inspect: Annotated[bool, inspect_opt] = False) -> None:
    """List workspaces and documents in a team"""
    st, res = the_grist.list_workspaces(team_id)
    _exit_if_error(st, res, inspect)
    if details:
        content = res
    else:
        table = Table('id', 'name', 'owner', 'email', 'docs')
        for ws in res:
            numdocs = len(ws.get('docs', []))
            table.add_row(str(ws['id']), ws['name'], str(ws['owner']['id']), 
                          ws['owner']['email'], str(numdocs))
        content = table
    _print_content(content, inspect)

@ws_app.command('new')
def add_ws(name: Annotated[str, typer.Argument(help='The name of new ws')], 
           team_id: Annotated[str, team_id_opt] = '',
           inspect: Annotated[bool, inspect_opt] = False) -> None:
    """Create an empty workspace"""
    st, res = the_grist.add_workspace(name, team_id)
    _exit_if_error(st, res, inspect)
    if inspect:
        cli_console.print(the_grist.inspect())
        cli_console.rule()
    cli_console.print(DONEMSG, 'Id:', res)

@ws_app.command('see')
def see_ws(ws_id: Annotated[int, ws_id_opt] = 0,
           details: Annotated[bool, details_opt] = False,
           inspect: Annotated[bool, inspect_opt] = False) -> None:
    """Describe a workspace"""
    st, res = the_grist.see_workspace(ws_id)
    _exit_if_error(st, res, inspect)
    if details:
        content = res
    else:
        table = Table('key', 'value')
        table.add_row('id', str(res['id']))
        table.add_row('name', res['name'])
        table.add_row('team', f"{res['org']['id']} - {res['org']['name']}")
        table.add_section()
        for doc in res.get('docs', []):
            table.add_row('doc', f"{doc['id']} - {doc['name']}")
        content = table
    _print_content(content, inspect)

@ws_app.command('update')
def update_ws(name: Annotated[str, typer.Argument(help='The new name')], 
              ws_id: Annotated[int, ws_id_opt] = 0,
              inspect: Annotated[bool, inspect_opt] = False) -> None:
    """Change the workspace name"""
    st, res = the_grist.update_workspace(name, ws_id)
    _print_done_or_exit(st, res, inspect)

@ws_app.command('delete')
def delete_ws(ws_id: Annotated[int, ws_id_opt] = 0,
              inspect: Annotated[bool, inspect_opt] = False) -> None:
    """Delete a workspace"""
    st, res = the_grist.delete_workspace(ws_id)
    _print_done_or_exit(st, res, inspect)

@ws_app.command('users')
def list_ws_users(ws_id: Annotated[int, ws_id_opt] = 0,  
                  details: Annotated[bool, details_opt] = False,
                  inspect: Annotated[bool, inspect_opt] = False) -> None:
    """List users with access to workspace"""
    st, res = the_grist.list_workspace_users(ws_id)
    _exit_if_error(st, res, inspect)
    content = res if details else _make_user_table(res)
    _print_content(content, inspect)

@ws_app.command('user-access')
def change_ws_access(uid: Annotated[int, typer.Argument(help='The user ID')], 
                     access: Annotated[str, access_opt],
                     ws_id: Annotated[int, ws_id_opt] = 0,
                     inspect: Annotated[bool, inspect_opt] = False) -> None:
    """Change user access level to a workspace"""
    st, res = the_grist.list_workspace_users(ws_id)
    _exit_if_error(st, res, inspect)
    usr_email = ''
    for usr in res:
        if usr['id'] == uid:
            usr_email = usr['email']
            break
    if not usr_email:
        if inspect:
            cli_console.print(the_grist.inspect())
            cli_console.rule()
        raise typer.BadParameter('User id not found.')
    users = {usr_email: access}
    st, res = the_grist.update_workspace_users(users, ws_id)
    _print_done_or_exit(st, res, inspect)
        
#TODO "change_user_access" is only for existing users, but "update_team_users"
# allows for adding users too. Maybe add a separate cli endpoint for this?

if __name__ == '__main__':
    app()
