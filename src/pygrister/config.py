import os, os.path
import json as modjson
from pprint import pformat

from pygrister.exceptions import GristApiNotConfigured

# This is the default Pygrister configuration.
# Use only non-empty strings as config values.

PYGRISTER_CONFIG = {
    'GRIST_API_KEY': '<your_api_key_here>',
    'GRIST_SELF_MANAGED': 'N',
    'GRIST_SELF_MANAGED_HOME': 'http://localhost:8484',
    'GRIST_SELF_MANAGED_SINGLE_ORG': 'Y',
    'GRIST_SERVER_PROTOCOL': 'https://',
    'GRIST_API_SERVER': 'getgrist.com',
    'GRIST_API_ROOT': 'api',
    'GRIST_TEAM_SITE': 'docs',
    'GRIST_WORKSPACE_ID': '0', # this should be a string castable to int
    'GRIST_DOC_ID': '<your_doc_id_here>',
    'GRIST_RAISE_ERROR': 'Y',
    'GRIST_SAFEMODE': 'N',
}

def apikey2output(apikey: str) -> str:
    """Obfuscate the secret Grist API key for output printing."""
    klen = len(apikey)
    return apikey if klen < 5 else f'{apikey[:2]}<{klen-4}>{apikey[-2:]}'


class Configurator:
    def __init__(self, config: dict[str, str]|None = None):
        self.config = dict()     # the actual, current configuration
        self.server = ''         # the current api server url
        self.raise_option = True # if we should raise Http errors
        self.safemode = False    # read-only mode
        self.reconfig(config)

    @staticmethod
    def get_config() -> dict[str, str]:
        """Return the Pygrister global configuration dictionary. 
        
        This is the "static" configuration setup, not counting anything 
        you may alter at runtime.
        Config keys are first searched in ``config.py``, then in 
        ``~/.gristapi/config.json``, and finally in matching env variables. 
        See ``config.py`` for a list of the config keys currently in use.
        """
        config = dict(PYGRISTER_CONFIG)
        pth = os.path.join(os.path.expanduser('~'), '.gristapi/config.json')
        if os.path.isfile(pth):
            with open(pth, 'r') as f:
                config.update(modjson.loads(f.read()))
        for k in config.keys():
            try:
                config[k] = os.environ[k]
            except KeyError:
                pass
        return config

    @staticmethod
    def config2output(config: dict[str, str], multiline: bool = False) -> str:
        """Format the Pygrister configuration as a string for output printing."""
        if not config: 
            return '{<empty>}'
        cfcopy = dict(config)
        cfcopy['GRIST_API_KEY'] = apikey2output(cfcopy.get('GRIST_API_KEY', ''))
        return pformat(cfcopy) if multiline else str(cfcopy)

    def reconfig(self, config: dict[str, str]|None = None) -> None:
        """Reload the configuration options. 
        
        Call this function if you have just updated config files/env. vars 
        at runtime, and/or pass a dictionary to the ``config`` parameter 
        to override existing config keys for the time being, eg.::

            grist.reconfig({'GRIST_TEAM_SITE': 'newteam'})

        now all future api calls will be directed to the new team site. 

        Note: this will re-build your configuration from scratch, then appy 
        the ``config`` parameter on top. To edit your *existent* configuration 
        instead, use the ``update_config`` function.
        """
        self.config = self.get_config()
        if config is not None:
            self.config.update(config)
        self._post_reconfig()

    def update_config(self, config: dict[str, str]) -> None:
        """Edit the configuration options.
        
        Call this function to edit your current runtime configuration: 
        pass a dictionary to the ``config`` parameter to override existing 
        config keys for the time being, eg.::

            grist.reconfig({'GRIST_TEAM_SITE': 'newteam'})

        now all future api calls will be directed to the new team site. 

        Note: this will apply the ``config`` parameter on top of your 
        existing configuration. To re-build the configuration from scratch, 
        use the ``reconfig`` function instead.
        """
        self.config.update(config)
        self._post_reconfig()

    def _post_reconfig(self): # check and cleanup after config is changed
        if not self.config or not all(self.config.values()):
            msg = f'Missing config values.\n{self.config2output(self.config)}'
            raise GristApiNotConfigured(msg)
        ws_id = self.config['GRIST_WORKSPACE_ID']
        try:
            _ = int(ws_id)
        except ValueError:
            msg = f'Workspace ID must be castable to integer, not "{ws_id}".'
            raise GristApiNotConfigured(msg)
        self.server = self.make_server()
        self.raise_option = (self.config['GRIST_RAISE_ERROR'] == 'Y')
        self.safemode = (self.config['GRIST_SAFEMODE'] == 'Y')

    def make_server(self, team_name: str = '') -> str:
        """Construct the "server" part of the API url, up to "/api". 
        
        A few options are possible, depending on the type of Grist hosting.
        The only moving part, as far as the GristApi class is concerned, 
        is the team name.
        """
        cf = self.config
        the_team = team_name or cf['GRIST_TEAM_SITE']
        if cf['GRIST_SELF_MANAGED'] == 'N':
            # the usual SaaS Grist: "https://myteam.getgrist.com/api"
            return f'{cf["GRIST_SERVER_PROTOCOL"]}{the_team}.' + \
                f'{cf["GRIST_API_SERVER"]}/{cf["GRIST_API_ROOT"]}'
        else:
            if cf['GRIST_SELF_MANAGED_SINGLE_ORG'] == 'Y':
                # self-managed, mono-team: "https://mygrist.com/api"
                return f'{cf["GRIST_SELF_MANAGED_HOME"]}/{cf["GRIST_API_ROOT"]}'
            else:
                # self-managed: "https://mygrist.com/o/myteam/api"
                return f'{cf["GRIST_SELF_MANAGED_HOME"]}/o/{the_team}' + \
                    f'/{cf["GRIST_API_ROOT"]}'

    def select_params(self, doc_id: str = '', team_id: str = ''):
        doc = doc_id or self.config['GRIST_DOC_ID']
        if not team_id:
            server = self.server
        else:
            server = self.make_server(team_name=team_id)
        return doc, server
