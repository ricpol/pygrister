# this is a first draft for a Pygrister cli. 
# with your normal "static" configuration in place, 
# you should be able to start a shell and type 
# $ gry see-team
# or 
# $ gry see-myself
# and something should happen... 

import os, os.path
import json as modjson
import typer
from rich import print

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

def _get_pygrist():
    c = _CliConfigurator()
    g = GristApi(custom_configurator=c)
    return g


app = typer.Typer()

@app.command()
def see_team(team_id: str = '') -> None:
    g = _get_pygrist()
    print(g.see_team()[1])

@app.command()
def see_myself() -> None:
    g = _get_pygrist()
    print(g.see_myself()[1])

if __name__ == '__main__':
    app()
