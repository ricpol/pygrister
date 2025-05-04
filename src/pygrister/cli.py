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
from rich import print
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

def _get_pygrist() -> GristApi:
    c = _CliConfigurator()
    g = GristApi(custom_configurator=c)
    return g

BADCALL = 3 # the exit code we reserve for bad call errors (eg http 404)
DONEMSG = '[green]Done.[/green]'
ERRMSG = '[bold red]Error![/bold red]'

# a few helper functions
# ----------------------------------------------------------------------
def _exit_with_error(st, res) -> None:
    print(ERRMSG, 'Status:', st, res)
    raise typer.Exit(BADCALL)

def _exit_if_error(st, res, ok) -> None:
    if not ok:
        print(ERRMSG, 'Status:', st, res)
        raise typer.Exit(BADCALL)

def _print_done_or_exit(st, res, ok) -> None:
    if ok: 
        print(DONEMSG)
    else:
        print(ERRMSG, 'Status:', st, res)
        raise typer.Exit(BADCALL)

def _print_user_table(response) -> None:
    console = Console()
    table = Table('id', 'name', 'email', 'access')
    for usr in response:
        table.add_row(str(usr['id']), usr['name'], usr['email'], 
                      str(usr['access']))
    console.print(table)

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
team_id_opt = typer.Option('--team', '-t', 
                           help='The team ID [default: current]')
ws_id_opt = typer.Option('--ws', '-w', 
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
def list_orgs() -> None:
    """List the teams you have access to"""
    g = _get_pygrist()
    st, res = g.list_team_sites()
    _exit_if_error(st, res, g.ok)
    console = Console()
    table = Table('id', 'name', 'owner')
    for org in res:
        table.add_row(str(org['id']), org['name'], org['owner']['name'])
    console.print(table)

@org_app.command('see')
def see_org(team_id: Annotated[str, team_id_opt] = '', 
            details: Annotated[bool, details_opt] = False) -> None:
    """Describe a team"""
    g = _get_pygrist()
    st, res = g.see_team(team_id)
    _exit_if_error(st, res, g.ok) 
    if details:
        print(res)
    else:
        console = Console()
        table = Table('key', 'value')
        table.add_row('id', str(res['id']))
        table.add_row('name', res['name'])
        table.add_row('domain', res['domain'])
        table.add_row('owner', f"{res['owner']['id']} - {res['owner']['name']}")
        console.print(table)

@org_app.command('update')
def update_org(name: Annotated[str, typer.Argument(help='The new name')], 
               team_id: Annotated[str, team_id_opt] = '') -> None:
    """Change the team name"""
    g = _get_pygrist()
    st, res = g.update_team(name, team_id)
    _print_done_or_exit(st, res, g.ok)
     
@org_app.command('delete')
def delete_org(team_id: Annotated[str, team_id_opt] = '') -> None:
    """Delete a team"""
    g = _get_pygrist()
    st, res = g.delete_team(team_id)
    _print_done_or_exit(st, res, g.ok)

@org_app.command('users')
def list_org_users(team_id: Annotated[str, team_id_opt] = '',  
                   details: Annotated[bool, details_opt] = False) -> None:
    """List users with access to team"""
    g = _get_pygrist()
    st, res = g.list_team_users(team_id)
    _exit_if_error(st, res, g.ok)
    if details:
        print(res)
    else:
        _print_user_table(res)

@org_app.command('user-access')
def change_team_access(uid: Annotated[int, typer.Argument(help='The user ID')], 
                       access: Annotated[str, access_opt],
                       team_id: Annotated[str, team_id_opt] = '') -> None:
    """Change user access level to a team"""
    g = _get_pygrist()
    st, res = g.list_team_users(team_id)
    _exit_if_error(st, res, g.ok)
    usr_email = ''
    for usr in res:
        if usr['id'] == uid:
            usr_email = usr['email']
            break
    if not usr_email:
        raise typer.BadParameter('User id not found.')
    users = {usr_email: access}
    st, res = g.update_team_users(users, team_id)
    _print_done_or_exit(st, res, g.ok)
        
#TODO "change_user_access" is only for existing users, but "update_team_users"
# allows for adding users too. Maybe add a separate cli endpoint for this?

# gry ws -> for managing workspaces
# ----------------------------------------------------------------------
@ws_app.command('list')
def list_ws(team_id: Annotated[str, team_id_opt] = '', 
            details: Annotated[bool, details_opt] = False) -> None:
    """List workspaces and documents in a team"""
    g = _get_pygrist()
    st, res = g.list_workspaces(team_id)
    _exit_if_error(st, res, g.ok)
    if details:
        print(res)
    else:
        console = Console()
        table = Table('id', 'name', 'owner', 'email', 'docs')
        for ws in res:
            numdocs = len(ws.get('docs', []))
            table.add_row(str(ws['id']), ws['name'], str(ws['owner']['id']), 
                          ws['owner']['email'], str(numdocs))
        console.print(table)

@ws_app.command('new')
def add_ws(name: Annotated[str, typer.Argument(help='The name of new ws')], 
           team_id: Annotated[str, team_id_opt] = '') -> None:
    """Create an empty workspace"""
    g = _get_pygrist()
    st, res = g.add_workspace(name, team_id)
    _exit_if_error(st, res, g.ok)
    print(DONEMSG, 'Id:', res)

@ws_app.command('see')
def see_ws(ws_id: Annotated[int, ws_id_opt] = 0,
           details: Annotated[bool, details_opt] = False) -> None:
    """Describe a workspace"""
    g = _get_pygrist()
    st, res = g.see_workspace(ws_id)
    _exit_if_error(st, res, g.ok)
    if details:
        print(res)
    else:
        console = Console()
        table = Table('key', 'value')
        table.add_row('id', str(res['id']))
        table.add_row('name', res['name'])
        table.add_row('team', f"{res['org']['id']} - {res['org']['name']}")
        table.add_section()
        for doc in res.get('docs', []):
            table.add_row('doc', f"{doc['id']} - {doc['name']}")
        console.print(table)

@ws_app.command('update')
def update_ws(name: Annotated[str, typer.Argument(help='The new name')], 
              ws_id: Annotated[int, ws_id_opt] = 0) -> None:
    """Change the workspace name"""
    g = _get_pygrist()
    st, res = g.update_workspace(name, ws_id)
    _print_done_or_exit(st, res, g.ok)

@ws_app.command('delete')
def delete_ws(ws_id: Annotated[int, ws_id_opt] = 0) -> None:
    """Delete a workspace"""
    g = _get_pygrist()
    st, res = g.delete_workspace(ws_id)
    _print_done_or_exit(st, res, g.ok)

@ws_app.command('users')
def list_ws_users(ws_id: Annotated[int, ws_id_opt] = 0,  
                  details: Annotated[bool, details_opt] = False) -> None:
    """List users with access to workspace"""
    g = _get_pygrist()
    st, res = g.list_workspace_users(ws_id)
    _exit_if_error(st, res, g.ok)
    if details:
        print(res)
    else:
        _print_user_table(res)

@ws_app.command('user-access')
def change_ws_access(uid: Annotated[int, typer.Argument(help='The user ID')], 
                     access: Annotated[str, access_opt],
                     ws_id: Annotated[int, ws_id_opt] = 0) -> None:
    """Change user access level to a workspace"""
    g = _get_pygrist()
    st, res = g.list_workspace_users(ws_id)
    _exit_if_error(st, res, g.ok)
    usr_email = ''
    for usr in res:
        if usr['id'] == uid:
            usr_email = usr['email']
            break
    if not usr_email:
        raise typer.BadParameter('User id not found.')
    users = {usr_email: access}
    st, res = g.update_workspace_users(users, ws_id)
    _print_done_or_exit(st, res, g.ok)
        
#TODO "change_user_access" is only for existing users, but "update_team_users"
# allows for adding users too. Maybe add a separate cli endpoint for this?

if __name__ == '__main__':
    app()
