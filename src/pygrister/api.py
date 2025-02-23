"""
Pygrister: a Python client for the Grist API.
=============================================

`Grist <https://www.getgrist.com/>`_ is a relational spreadsheet with tons of 
batteries included. The Grist API allows you to programmatically retrieve/update 
your data stored on Grist, and manipulate most of the basic Grist objects, 
such as workspaces, documents, user permissions and so on. 

Pygrister is a basic Grist client, wrapping all the documented APIs. 
Pygrister keeps track of some configuration for you, remembering your 
team site, workspace, working document, so that you don't have to type in 
the boring stuff every time. Apart from that and little else, Pygrister 
is rather low-level: it will call the api and retrieve the response "as is". 
If the api call is malformed, you will simply receive a bad HTTP status code. 

Pygrister will not attempt to convert sent and received data types: 
however, it will execute custom converter functions, if provided.

Basic usage goes as follows::

    from pygrister.api import GristApi

    grist = GristApi()
    # list users/permissions for the current document
    status_code, response = grist.list_doc_users()
    # fetch all rows in a table
    status_code, response = grist.see_records('Table1') 
    # add a column to a table
    cols = [{'id': 'age', 'fields': {'label':'age', 'type': 'Int'}}]
    status_code, response = grist.add_cols('Table1', cols) 

You should `read the documentation <https://pygrister.readthedocs.io>`_ 
first, to learn about the basic Pygrister concepts, patterns and configurations. 
However, the api call functions themselves are not documented in Pygrister: 
see the `Grist API reference documentation <https://support.getgrist.com/api/>`_ 
for details about each api signature, and browse the Pygrister test suite 
for more usage examples.

"""
from __future__ import annotations

import os, os.path
import json as modjson # "json" is a common name for request params...
import functools
from urllib.parse import urlencode, quote
from pprint import pformat
from typing import Any

from requests import request, Session, JSONDecodeError

from pygrister.config import PYGRISTER_CONFIG

MAXSAVEDRESP = 5000 #: max length of resp. content, saved for inspection
SAVEBINARYRESP = False #: if binary resp. content should be saved for inspection

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

def apikey2output(apikey: str) -> str:
    """Obfuscate the secret Grist API key for output printing."""
    klen = len(apikey)
    return apikey if klen < 5 else f'{apikey[:2]}<{klen-4}>{apikey[-2:]}'

def config2output(config: dict[str, str], multiline: bool = False) -> str:
    """Format the Pygrister configuration as a string for output printing."""
    if not config: 
        return '{<empty>}'
    cfcopy = dict(config)
    cfcopy['GRIST_API_KEY'] = apikey2output(cfcopy.get('GRIST_API_KEY', ''))
    return pformat(cfcopy) if multiline else str(cfcopy)


class GristApiException(Exception): 
    """The base GristApi exception."""
    pass

class GristApiNotConfigured(GristApiException): 
    """A configuration error occurred."""
    pass

class GristApiNotImplemented(GristApiException): 
    "This API is not yet implemented by Pygrister."""
    pass

class GristApiInSafeMode(GristApiException): 
    """Pygrister is in safe mode, no writing to the db is possible."""
    pass


def check_safemode(funct):
    """If Pygrister is in safemode, no writing API call will pass through."""
    @functools.wraps(funct)
    def wrapper(self, *a, **k):
        if self.safemode:
            msg = 'GristApi is in safe mode: you cannot write to db. '
            msg += f'Configuration:\n{config2output(self._config, True)}'
            raise GristApiInSafeMode(msg)
        return funct(self, *a, **k)
    return wrapper

Apiresp = tuple[int, Any] #: the return type of all api call functions

class Paginator:
    """A simple iterable object to wrap Api calls that needs pagination."""
    def __init__(self, provider, start, items, lenname, 
                 res_transform, **query_args):
        self.provider = provider # the GristApi method that will handle the call
        self.index = start # start index for pagination
        self.items = items # number of items to retrieve
        self.lenname = lenname # the res dict key storing the total num of items
        self.res_transform = res_transform # a callable to clean up the call result
        self.query_args = query_args # any other arg to be passed to the call
        self.num_items = 0 # the total num of items

    def __len__(self): 
        return self.num_items
    
    def __iter__(self): 
        return self

    def __next__(self):        
        st, res = self.provider(self.index, self.items, **self.query_args)
        self.num_items = int(res[self.lenname])
        if self.index > self.num_items:
            raise StopIteration
        self.index += self.items
        return st, self.res_transform(res)
      

class GristApi:
    def __init__(self, config: dict[str, str]|None = None,
                 in_converter: dict|None = None, 
                 out_converter: dict|None = None, 
                 request_options: dict|None = None):
        self.reconfig(config)
        self.apicalls: int = 0            #: total number of API calls
        self.ok: bool = True              #: if an HTTPError occurred
        self.req_url: str = ''            #: last request url
        self.req_body: str = ''           #: last request body
        self.req_headers: dict = dict()   #: last request headers
        self.req_method: str = ''         #: last request method
        self.resp_content: str|bytes = '' #: last response content
        self.resp_code: str = ''          #: last response status code
        self.resp_reason: str = ''        #: last response status reason
        self.resp_headers: dict = dict()  #: last reponse headers
        self.session = None               #: Requests session object, or None
        self.in_converter = {}            #: converters for input data
        self.out_converter = {}           #: converters for output data
        self.request_options = {}         #: other options to pass to request
        if in_converter:
            self.in_converter = in_converter
        if out_converter:
            self.out_converter = out_converter
        if request_options:
            self.request_options = request_options

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
        self._config = get_config()
        if config is not None:
            self._config.update(config)
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
        self._config.update(config)
        self._post_reconfig()

    def _post_reconfig(self): # check and cleanup after config is changed
        if not self._config or not all(self._config.values()):
            msg = f'Missing config values.\n{config2output(self._config)}'
            raise GristApiNotConfigured(msg)
        self.server = self.make_server()
        self.raise_option = (self._config['GRIST_RAISE_ERROR'] == 'Y')
        self.safemode = (self._config['GRIST_SAFEMODE'] == 'Y')

    def make_server(self, team_name: str = '') -> str:
        """Construct the "server" part of the API url, up to "/api". 
        
        A few options are possible, depending on the type of Grist hosting.
        The only moving part, as far as the GristApi class is concerned, 
        is the team name.
        """
        cf = self._config
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

    def _select_params(self, doc_id: str = '', team_id: str = ''):
        doc = doc_id or self._config['GRIST_DOC_ID']
        if not team_id:
            server = self.server
        else:
            server = self.make_server(team_name=team_id)
        return doc, server

    def open_session(self):
        if self.session:
            self.session.close()
        self.session = Session()
    
    def close_session(self):
        if self.session:
            self.session.close()
        self.session = None
    
    def apicall(self, url: str, method: str = 'GET', headers: dict|None = None, 
                params: dict|None = None, json: dict|None = None, 
                filename: str = '') -> Apiresp:
        self.apicalls += 1
        call = self.session.request if self.session else request
        if headers is None:
            headers = {'Content-Type': 'application/json',
                       'Accept': 'application/json'}
        headers.update(
            {'Authorization': f'Bearer {self._config["GRIST_API_KEY"]}'})

        if not filename:  # ordinary request
            resp = call(method, url, headers=headers, params=params, 
                        json=json, **self.request_options) 
            self.ok = resp.ok
            self._save_request_data(resp)
            if self.raise_option:
                resp.raise_for_status()
            return resp.status_code, resp.json() if resp.content else None
        else:
            if method == 'GET': # download mode
                with call(method, url, headers=headers, params=params, 
                          stream=True, **self.request_options) as resp:
                    self.ok = resp.ok
                    self._save_request_data(resp)
                    if self.raise_option:
                        resp.raise_for_status()
                    if resp.ok:
                        with open(filename, 'wb') as f:
                            for chunk in resp.iter_content(chunk_size=1024*100):
                                f.write(chunk)
                return resp.status_code, None
            else: # 'POST', upload mode
                # TODO headers and the "upload" bit below  
                # are too coupled with the specific needs of upload_attachment;
                with open(filename, 'rb') as f:
                    resp = call(method, url, headers=headers, 
                                files={'upload': f}, **self.request_options)
                self.ok = resp.ok
                self._save_request_data(resp)
                if self.raise_option:
                    resp.raise_for_status()
                return resp.status_code, resp.json() if resp.content else None

    def _save_request_data(self, response):
        self.req_url = response.request.url
        self.req_body = response.request.body
        self.req_headers = response.request.headers
        self.req_method = response.request.method
        if response.content:
            try:
                self.resp_content = str(response.json())[:MAXSAVEDRESP]
            except JSONDecodeError:
                if SAVEBINARYRESP:
                    self.resp_content = response.content[:MAXSAVEDRESP]
                else:
                    self.resp_content = '<not a valid json>'
        else:
            self.resp_content = '<no response body>'
        self.resp_code = response.status_code
        self.resp_reason = response.reason
        self.resp_headers = response.headers

    def inspect(self) -> str:
        """Collect useful info about the last api call that was sent. 
        
        Intended for debug: add a ``print(self.inspect())`` after 
        something went wrong. Works after an HTTPError too.
        """
        hdcopy = dict(self.req_headers)
        prot, key = hdcopy['Authorization'].split()
        key = apikey2output(key)
        hdcopy['Authorization'] = f'{prot} {key}'
        txt = f'->Url: {self.req_url}\n'
        txt += f'->Method: {self.req_method}\n'
        txt += f'->Headers: {hdcopy}\n'
        txt += f'->Body: {self.req_body}\n'
        txt += f'->Response: {self.resp_code}, {self.resp_reason}\n'
        txt += f'->Resp. headers: {self.resp_headers}\n'
        txt += f'->Resp. content: {self.resp_content}\n'
        txt += f'->Config: {config2output(self._config)}'
        return txt

    # USERS (/scim/v2 and /user endpoints)
    # ------------------------------------------------------------------

    def see_user(self, user_id: int) -> Apiresp:
        """Implement GET ``/scim/v2/Users/{userId}``. 
        
        If successful, response will be a ``dict`` of user details. 
        If scim is not enabled, will return Http 501.
        """
        url = f'{self.server}/scim/v2/Users/{user_id}'
        return self.apicall(url, 
                            headers={'Content-Type': 'application/scim+json'})

    def see_myself(self) -> Apiresp:
        """Implement GET ``/scim/v2/Me``. 
        
        If successful, response will be a ``dict`` of logged-in user's details. 
        If scim is not enabled, will return Http 501.
        """
        url = f'{self.server}/scim/v2/Me'
        return self.apicall(url,
                            headers={'Content-Type': 'application/scim+json'})

    def list_users(self, start: int = 1, chunk: int = 10, 
                   filter: str = '') -> Paginator:
        """Implement GET ``/scim/v2/Users``. 
        
        This is a paginated api: return an iterable object which, in turn, 
        will retrieve ``chunk`` users at a time, as a ``list[dict]``. 
        """
        return Paginator(self.list_users_raw, start, chunk, 'totalResults', 
                          lambda res: res['Resources'], filter=filter)

    def list_users_raw(self, start: int = 1, chunk: int = 10, 
                       filter: str = '') -> Apiresp:
        """Implement GET ``/scim/v2/Users``. 
        
        If successful, response will be a ``dict`` of user data. 
        If scim is not enabled, will return Http 501.
        """
        url = f'{self.server}/scim/v2/Users'
        headers = {'Content-Type': 'application/scim+json'}
        if filter:
            # Requests will *form*-encode the filter, Grist want it *url*-encoded
            # instead, so we need to skip Request and manually compose the url
            params = {'startIndex': start, 'count': chunk, 
                      'filter': modjson.dumps(filter)}
            encoded_params = urlencode(params, quote_via=quote)
            st, res = self.apicall(url+'?'+encoded_params, headers=headers)
        else:
            # the usual way
            st, res = self.apicall(url, headers=headers, 
                                   params={'startIndex': start, 'count': chunk})
        return st, res

    def _make_user_data(self, username, emails, formatted_name, display_name, 
                        lang, locale, photos, schemas) -> dict: 
        # compose json payload for a scim user
        if schemas is None: 
            schemas = ['urn:ietf:params:scim:schemas:core:2.0:User']
        json = {'userName': username, 'name': {'formatted': ''}, 
                'locale': locale, 'preferredLanguage': lang, 'schemas': schemas}
        json['displayName'] = display_name or username
        json['name']['formatted'] = formatted_name or display_name or username
        ml = [{'value': m, 'primary': False} for m in emails]
        ml[0]['primary'] = True
        json['emails'] = ml
        if photos:
            ph = [{'value': ph, 'primary': False, 'type': 'photo'} 
                  for ph in photos]
            ph[0]['primary'] = True
            json['photos'] = ph
        return json

    @check_safemode
    def add_user(self, username: str, emails: list[str],
                 formatted_name: str = '', display_name: str = '', 
                 lang: str = 'en', locale: str = 'en', 
                 photos: list[str]|None = None, schemas: list[str]|None = None 
                 ) -> Apiresp:
        """Implement POST ``/scim/v2/Users``. 

        Note: ``schemas`` defaults to 
        ['urn:ietf:params:scim:schemas:core:2.0:User']

        If successful, response will be the user id as an ``int``. 
        If scim is not enabled, will return Http 501.
        """
        json = self._make_user_data(username, emails, formatted_name, 
                                    display_name,lang, locale, photos, schemas)
        url = f'{self.server}/scim/v2/Users'
        st, res = self.apicall(url, 'POST', json=json, 
                               headers={'Content-Type': 'application/scim+json'})
        try:
            return st, int(res['id'])
        except KeyError:
            return st, res

    @check_safemode
    def update_user_override(self, user_id: int, username: str, emails: list[str],
                             formatted_name: str = '', display_name: str = '', 
                             lang: str = 'en', locale: str = 'en', 
                             photos: list[str]|None = None, 
                             schemas: list[str]|None = None) -> Apiresp:
        """Implement PUT ``/scim/v2/Users/{userId}``. 
        
        Note: ``schemas`` defaults to 
        ['urn:ietf:params:scim:schemas:core:2.0:User']

        If successful, response will be ``None``. 
        If scim is not enabled, will return Http 501.
        """
        json = self._make_user_data(username, emails, formatted_name, 
                                    display_name,lang, locale, photos, schemas)
        url = f'{self.server}/scim/v2/Users/{user_id}'
        st, res = self.apicall(url, 'PUT', json=json, 
                               headers={'Content-Type': 'application/scim+json'})
        try:
            _ = res['id']
            return st, None
        except KeyError:
            return st, res

    @check_safemode
    def update_user(self, user_id: int, operations: list[dict], 
                    schemas: list[str]|None = None) -> Apiresp:
        """Implement PATCH ``/scim/v2/Users/{userId}``. 
        
        Note: ``schemas`` defaults to 
        ['urn:ietf:params:scim:api:messages:2.0:PatchOp']

        If successful, response will be ``None``. 
        If scim is not enabled, will return Http 501.
        """
        if schemas is None:
            schemas = ['urn:ietf:params:scim:api:messages:2.0:PatchOp']
        json = {'Operations': operations, 'schemas': schemas}
        url = f'{self.server}/scim/v2/Users/{user_id}'
        st, res = self.apicall(url, 'PATCH', json=json, 
                               headers={'Content-Type': 'application/scim+json'})
        try:
            _ = res['id']
            return st, None
        except KeyError:
            return st, res
        
    @check_safemode
    def delete_user(self, user_id: int):
        """Implement DELETE ``/scim/v2/Users/{userId}``. 
        
        If successful, response will be ``None``. 
        If scim is not enabled, will return Http 501.
        """
        url = f'{self.server}/scim/v2/Users/{user_id}'
        return self.apicall(url, 'DELETE', 
                            headers={'Content-Type': 'application/scim+json'})

    @check_safemode
    def delete_myself(self, user: str, doc_id: str = '', 
                      team_id: str = '') -> Apiresp:
        """Implement DELETE ``/users/{userId}``.

        Note: since this is the only /users endpoint implemented by Grist 
        right now, and since it is of little help (you can only delete 
        your own account), we choose not to implement this one, and leave 
        it here as a stub. 
        """
        raise GristApiNotImplemented
        # the following is a stub implementation:
        # doc_id, server = self._select_params(doc_id, team_id)
        # url = f'{server}/users/{user}'
        # st, res = self.apicall(url, 'DELETE')
        # if st <= 200:
        #     return st, None 
        # else:
        #     return st, res

    def search_users(self, start: int = 1, chunk: int = 10, 
                     sort: str = '', asc: bool = True, filter: str = '', 
                     attrib: list[str]|None = None, 
                     no_attrib: list[str]|None = None, 
                     schemas: list[str]|None = None) -> Paginator:
        """Implement POST ``/scim/v2/Users/.search``. 
        
        Note: ``schemas`` defaults to 
        ['urn:ietf:params:scim:api:messages:2.0:BulkRequest']

        This is a paginated api: return an iterable object which, in turn, 
        will retrieve ``chunk`` users at a time, as a ``list[dict]``. 
        """
        return Paginator(self.search_users_raw, start, chunk, 'totalResults', 
                          lambda res: res['Resources'],
                          sort=sort, asc=asc, filter=filter, attrib=attrib, 
                          no_attrib=no_attrib, schemas=schemas)

    def search_users_raw(self, start: int = 1, chunk: int = 10, 
                         sort: str = '', asc: bool = True, filter: str = '', 
                         attrib: list[str]|None = None, 
                         no_attrib: list[str]|None = None, 
                         schemas: list[str]|None = None) -> Apiresp:
        """Implement POST ``/scim/v2/Users/.search``. 
        
        Note: ``schemas`` defaults to 
        ['urn:ietf:params:scim:api:messages:2.0:BulkRequest']

        If successful, response will be a ``dict`` of user data. 
        If scim is not enabled, will return Http 501. 
        """
        url = f'{self.server}/scim/v2/Users/.search'
        headers = {'Content-Type': 'application/scim+json'}
        if schemas is None:
            schemas = ['urn:ietf:params:scim:api:messages:2.0:SearchRequest']
        json = {'startIndex': start, 'count': chunk, 'schemas': schemas}
        if filter:
            json['filter'] = filter
        if sort:
            sortorder = ('descending', 'ascending')[int(asc)]
            json['sortBy'] = sort
            json['sortOrder'] = sortorder
        if attrib is not None:
            json['attributes'] = attrib
        if no_attrib is not None:
            json['excludedAttributes'] = no_attrib
        return self.apicall(url, 'POST', headers=headers, json=json)

    @check_safemode
    def bulk_users(self, operations: list[dict], 
                   schemas: list[str]|None = None) -> Apiresp:
        """Implement POST ``/scim/v2/Bulk``. 

        Note: ``schemas`` defaults to 
        ['urn:ietf:params:scim:api:messages:2.0:BulkRequest']

        If successful, response will be a ``list[int]`` of status codes for 
        each operation (inspect ``GristApi.resp_content`` for details, 
        if any operations resulted in a bad status code).
        If scim is not enabled, will return Http 501.
        """
        if schemas is None:
            schemas = ['urn:ietf:params:scim:api:messages:2.0:BulkRequest']
        json = {'Operations': operations, 'schemas': schemas}
        url = f'{self.server}/scim/v2/Bulk'
        st, res = self.apicall(url, 'POST', json=json, 
                               headers={'Content-Type': 'application/scim+json'})
        if st == 200:
            return st, [int(i['status']) for i in res['Operations']]
        else:
            return st, res

    def see_scim_schemas(self):
        """Implement GET ``/scim/v2/Schemas``. 
        
        If successful, response will a ``dict`` of scim schemas. 
        If scim is not enabled, will return Http 501.
        """
        url = f'{self.server}/scim/v2/Schemas'
        return self.apicall(url, 
                            headers={'Content-Type': 'application/scim+json'})

    def see_scim_config(self):
        """Implement GET ``/scim/v2/ServiceProviderConfig``. 
        
        If successful, response will a ``dict`` of scim provider configuration. 
        If scim is not enabled, will return Http 501.
        """
        url = f'{self.server}/scim/v2/ServiceProviderConfig'
        return self.apicall(url, 
                            headers={'Content-Type': 'application/scim+json'})

    def see_scim_resources(self):
        """Implement GET ``/scim/v2/ResourceTypes``. 
        
        If successful, response will a ``dict`` of scim resources. 
        If scim is not enabled, will return Http 501.
        """
        url = f'{self.server}/scim/v2/ResourceTypes'
        return self.apicall(url, 
                            headers={'Content-Type': 'application/scim+json'})

    # TEAM SITES (organisations)
    # ------------------------------------------------------------------

    def list_team_sites(self) -> Apiresp:
        """Implement GET ``/orgs``.
        
        If successful, response will be a ``list[dict]`` of site details.
        """
        url = f'{self.server}/orgs'
        return self.apicall(url)
    
    def see_team(self, team_id: str = '') -> Apiresp:
        """Implement GET ``/orgs/{orgId}``.
        
        If successful, response will be a ``dict`` of site details.
        """
        team_id = team_id or 'current'
        url = f'{self.server}/orgs/{team_id}'
        return self.apicall(url)

    @check_safemode
    def update_team(self, new_name: str, team_id: str = '') -> Apiresp:
        """Implement PATCH ``/orgs/{orgId}``.
       
        If successful, response will be ``None``.
        Note that renaming a team will *not* change the subdomain too!
        """
        team_id = team_id or 'current'
        url = f'{self.server}/orgs/{team_id}'
        json = {'name': new_name}
        return self.apicall(url, method='PATCH', json=json)

    def list_team_users(self, team_id: str = '') -> Apiresp:
        """Implement GET ``/orgs/{orgId}/access``.
        
        If successful, response will be a ``list[dict]`` of users.
        """
        team_id = team_id or 'current'
        url = f'{self.server}/orgs/{team_id}/access'
        st, res = self.apicall(url)
        try:
            return st, res['users']
        except KeyError:
            return st, res

    @check_safemode
    def update_team_users(self, users: dict[str, str], 
                          team_id: str = '') -> Apiresp:
        """Implement PATCH ``/orgs/{orgId}/access``.
        
        If successful, response will be ``None``.
        """
        team_id = team_id or 'current'
        json = {'delta': {'users': users}}
        url = f'{self.server}/orgs/{team_id}/access'
        return self.apicall(url, 'PATCH', json=json)

    # WORKSPACES
    # ------------------------------------------------------------------

    def list_workspaces(self, team_id: str = '') -> Apiresp:
        """Implement GET ``/{orgId}/workspaces``.
        
        If successful, response will be a ``list[dict]`` of workspaces.
        """
        team_id = team_id or 'current'
        url = f'{self.server}/orgs/{team_id}/workspaces'
        return self.apicall(url)

    @check_safemode
    def add_workspace(self, name: str, team_id: str = '') -> Apiresp:
        """Implement POST ``/{orgId}/workspaces``.
        
        If successful, response will be the workspace id as an ``int``.
        """
        team_id = team_id or 'current'
        url = f'{self.server}/orgs/{team_id}/workspaces'
        json = {'name': name}
        return self.apicall(url, method='POST', json=json)

    def see_workspace(self, ws_id: int = 0) -> Apiresp: 
        """Implement GET ``/workspaces/{workspaceId}``.
        
        If successful, response will be a ``dict`` of workspace details.
        """
        ws_id = ws_id or int(self._config['GRIST_WORKSPACE_ID'])
        url = f'{self.server}/workspaces/{ws_id}'
        return self.apicall(url)

    @check_safemode
    def update_workspace(self, new_name: str, ws_id: int = 0) -> Apiresp: 
        """Implement PATCH ``/workspaces/{workspaceId}``.
        
        If successful, response will be ``None``.
        """
        ws_id = ws_id or int(self._config['GRIST_WORKSPACE_ID'])
        url = f'{self.server}/workspaces/{ws_id}'
        json = {'name': new_name}
        st, res = self.apicall(url, method='PATCH', json=json)
        if res == ws_id:
            res = None
        return st, res

    @check_safemode
    def delete_workspace(self, ws_id: int = 0) -> Apiresp:
        """Implement DELETE ``/workspaces/{workspaceId}``.
        
        If successful, response will be ``None``.
        """
        # it's safer to ask for a workspace id here
        url = f'{self.server}/workspaces/{ws_id}'
        st, res = self.apicall(url, method='DELETE')
        if res == ws_id:
            res = None
        return st, res

    def list_workspace_users(self, ws_id: int = 0) -> Apiresp:
        """Implement GET ``/workspaces/{workspaceId}/access``.
        
        If successful, response will be a ``list[dict]`` of users.
        """
        ws_id = ws_id or int(self._config['GRIST_WORKSPACE_ID'])
        url = f'{self.server}/workspaces/{ws_id}/access'
        st, res = self.apicall(url)
        try:
            # note: we leave out the 'maxInheritedRole' information here!
            return st, res['users']
        except KeyError:
            return st, res

    @check_safemode
    def update_workspace_users(self, users: dict[str, str], 
                               ws_id: int = 0) -> Apiresp:
        """Implement PATCH ``/workspaces/{workspaceId}/access``.
        
        If successful, response will be ``None``.
        """
        ws_id = ws_id or int(self._config['GRIST_WORKSPACE_ID'])
        json = {'delta': {'users': users}}
        url = f'{self.server}/workspaces/{ws_id}/access'
        return self.apicall(url, 'PATCH', json=json)

    # DOCUMENTS
    # ------------------------------------------------------------------

    @check_safemode
    def add_doc(self, name: str, pinned: bool = False, 
                ws_id: int = 0) -> Apiresp:
        """Implement POST ``/workspaces/{workspaceId}/docs``.
        
        If successful, response will be the doc id as a ``str``.
        """
        ws_id = ws_id or int(self._config['GRIST_WORKSPACE_ID'])
        json = {'name': name, 'isPinned': pinned}
        url = f'{self.server}/workspaces/{ws_id}/docs'
        return self.apicall(url, method='POST', json=json)

    def see_doc(self, doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}``.
        
        If successful, response will be a ``dict`` of doc details.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}'
        return self.apicall(url)

    @check_safemode
    def update_doc(self, new_name: str = '', pinned: bool = False, 
                   doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}'
        json = {'isPinned': pinned}
        if new_name:
            json.update({'name': new_name}) # type:ignore
        st, res = self.apicall(url, method='PATCH', json=json)
        if res == doc_id:
            res = None
        return st, res

    @check_safemode
    def delete_doc(self, doc_id: str, team_id: str = '') -> Apiresp:
        """Implement DELETE ``/docs/{docId}``.
        
        If successful, response will be ``None``.
        """
        # it's safer to ask for a doc id here
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}'
        st, res = self.apicall(url, method='DELETE')
        if res == doc_id:
            res = None
        return st, res
        
    @check_safemode
    def move_doc(self, ws_id: int, doc_id: str = '', 
                 team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}/move``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/move'
        json = {'workspace': ws_id}
        st, res = self.apicall(url, method='PATCH', json=json)
        if res == doc_id:
            res = None
        return st, res

    def list_doc_users(self, doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/access``.
        
        If successful, response will be a ``list[dict]`` of users.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/access'
        st, res = self.apicall(url)
        try:
            # note: we leave out the 'maxInheritedRole' information here!
            return st, res['users']
        except KeyError:
            return st, res

    @check_safemode
    def update_doc_users(self, users: dict[str, str], max: str = 'owners', 
                         doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}/access``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        json = {'delta': {'maxInheritedRole': max, 'users': users}}
        url = f'{server}/docs/{doc_id}/access'
        return self.apicall(url, 'PATCH', json=json)

    def download_sqlite(self, filename: str, nohistory: bool = False, 
                        template: bool = False, doc_id: str = '', 
                        team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/download``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/download'
        headers = {'Accept': 'application/x-sqlite3'}
        params = {'nohistory': nohistory, 'template': template}
        return self.apicall(url, headers=headers, params=params, 
                            filename=filename)

    def download_excel(self, filename: str, table_id: str, 
                       header: str = 'label', doc_id: str = '', 
                       team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/download/xlsx``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/download/xlsx'
        headers = {'Accept': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
        params = {'header': header, 'tableId': table_id}
        return self.apicall(url, headers=headers, params=params, 
                            filename=filename)

    def download_csv(self, filename: str, table_id: str, 
                     header: str = 'label', doc_id: str = '', 
                     team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/download/csv``.
        
        If successful, response will be ``None``.
        """
        # note: the grist api also puts the data in the response body...
        # we just download the file and return None instead
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/download/csv'
        headers = {'Accept': 'text/csv'}
        params = {'header': header, 'tableId': table_id}
        return self.apicall(url, headers=headers, params=params, 
                            filename=filename)

    def download_schema(self, table_id: str, header: str = 'label',
                        filename: str = '', doc_id: str = '', 
                        team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/download/table-schema``.
        
        If successful, schema will be returned as json; pass the `filename` 
        param to have it downloaded as a json file instead.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        params = {'tableId': table_id, 'header': header}
        url = f'{server}/docs/{doc_id}/download/table-schema'
        headers = {'Accept': 'text/csv'}
        return self.apicall(url, headers=headers, params=params, 
                            filename=filename)

    # RECORDS
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_out_converter(records: list[dict], converter: dict):
        for rec in records:
            for k, v in rec.items():
                try:
                    rec[k] = converter[k](v)
                except KeyError:
                    pass
                except (TypeError, ValueError): # if converter fails, we return...
                    if v is not None:           # ...either None...
                        rec[k] = str(v)         # ...or a string
        return records

    @staticmethod
    def _apply_in_converter(records: list[dict], converter: dict, 
                            is_add_update: bool = False):
        # call with "is_add_update=True" only from add_update_records
        # it's a hack to compensate for the different record schema
        for rec in records:
            the_record = rec if not is_add_update else rec['fields']
            for k, v in the_record.items():
                try:  # note: we prefer not to catch Type/ValueErrors here
                    the_record[k] = converter[k](v)
                except KeyError:
                    pass
        return records

    def list_records(self, table_id: str, filter: dict|None = None, 
                     sort: str = '', limit: int = 0, hidden: bool = False, 
                     doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/tables/{tableId}/records``.
        
        If a converter is found for this table, data conversion will be 
        attempted. If successful, response will be a list of "Pygrister 
        records with id" (see docs). 
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/records'
        headers = {'X-Sort': sort, 'X-Limit': str(limit)}
        if filter:
            # Requests will *form*-encode the filter, Grist want it *url*-encoded
            # instead, so we need to skip Request and manually compose the url
            params = {'hidden': hidden, 'filter': modjson.dumps(filter)}
            encoded_params = urlencode(params, quote_via=quote)
            st, res = self.apicall(url+'?'+encoded_params, headers=headers)
        else:
            # the usual way
            st, res = self.apicall(url, headers=headers, 
                                   params={'hidden': hidden})
        try:
            records = [{'id': r['id']}|r['fields'] for r in res['records']]
        except KeyError: # an error occurred
            return st, res
        try:
            converter = self.out_converter[table_id]
        except KeyError: # no converter for this table
            return st, records
        return st, self._apply_out_converter(records, converter)

    @check_safemode
    def add_records(self, table_id: str, records: list[dict], 
                    noparse: bool = False, doc_id: str = '', 
                    team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/tables/{tableId}/records``.
        
        ``records``: a list of "Pygrister records without id" (see docs).
        If a converter is found for this table, data conversion will be 
        attempted. If successful, response will be a ``list[int]`` of 
        added record ids.
        """
        converter = self.in_converter.get(table_id, None)
        if converter is not None: 
            records = self._apply_in_converter(records, converter)
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/records'
        params = {'noparse': noparse}
        json = {'records': [{'fields': r} for r in records]}
        st, res = self.apicall(url, 'POST', params=params, json=json)
        try:
            return st, [i['id'] for i in res['records']]
        except KeyError:
            return st, res

    @check_safemode
    def update_records(self, table_id: str, records: list[dict], 
                       noparse: bool = False, doc_id: str = '', 
                       team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}/tables/{tableId}/records``.

        ``records``: a list of "Pygrister records with id" (see docs).
        If a converter is found for this table, data conversion will be 
        attempted. If successful, response will be ``None``.
        """
        converter = self.in_converter.get(table_id, None)
        if converter is not None: 
            records = self._apply_in_converter(records, converter)
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/records'
        params = {'noparse': noparse}
        json = {'records': [{'id': rec.pop('id'), 'fields': rec} 
                            for rec in records]}
        return self.apicall(url, 'PATCH', params=params, json=json)

    @check_safemode
    def add_update_records(self, table_id: str, records: list[dict], 
                           noparse: bool = False, onmany: str = 'first', 
                           noadd: bool = False, noupdate: bool = False, 
                           allow_empty_require: bool = False, 
                           doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement PUT ``/docs/{docId}/tables/{tableId}/records``.
        
        If a converter is found for this table, data conversion will be 
        attempted. If successful, response will be ``None``.
        """
        converter = self.in_converter.get(table_id, None)
        if converter is not None: 
            records = self._apply_in_converter(records, converter, True)
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/records'
        params = {'noparse': noparse, 'onmany': onmany, 'noadd': noadd, 
                  'noupdate': noupdate, 'allow_empty_require': allow_empty_require}
        json = {'records': records}
        return self.apicall(url, 'PUT', params=params, json=json)

    # TABLES
    # ------------------------------------------------------------------

    def list_tables(self, doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/tables``.
        
        If successful, response will be a ``list[dict]`` of tables.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables'
        st, res = self.apicall(url)
        try:
            return st, res['tables']
        except KeyError:
            return st, res
    
    @check_safemode
    def add_tables(self, tables: list[dict], doc_id: str = '', 
                   team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/tables``.
        
        If successful, response will be a ``list[str]`` of added table ids.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables'
        json = {'tables': tables}
        st, res = self.apicall(url, 'POST', json=json)
        try:
            return st, [i['id'] for i in res['tables']]
        except KeyError:
            return st, res
        
    @check_safemode
    def update_tables(self, tables: list[dict], doc_id: str = '', 
                      team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}/tables``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables'
        json = {'tables': tables}
        return self.apicall(url, 'PATCH', json=json)

    # COLUMNS
    # ------------------------------------------------------------------

    def list_cols(self, table_id: str, hidden: bool = False, 
                  doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/tables/{tableId}/columns``.
        
        If successful, response will be a ``list[dict]`` of columns.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/columns'
        params = {'hidden': hidden}
        st, res = self.apicall(url, params=params)
        try:
            return st, res['columns']
        except KeyError:
            return st, res

    @staticmethod
    def _jsonize_col_options(cols: list[dict]) -> list[dict]:
        # this is needed for column manipulation:
        # if a "widgetOptions" field is present, the nested dict must be 
        # json-ized first! See the example in the Grist api console
        for col in cols:
            try:
                col['fields']['widgetOptions'] = \
                                modjson.dumps(col['fields']['widgetOptions'])
            except KeyError:
                pass
        return cols

    @check_safemode
    def add_cols(self, table_id: str, cols: list[dict], 
                 doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/tables/{tableId}/columns``.
        
        If successful, response will be a ``list[str]`` of added col ids.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/columns'
        cols = self._jsonize_col_options(cols)
        json = {'columns': cols}
        st, res = self.apicall(url, 'POST', json=json)
        try:
            return st, [i['id'] for i in res['columns']]
        except KeyError:
            return st, res

    @check_safemode
    def update_cols(self, table_id: str, cols: list[dict], 
                    doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}/tables/{tableId}/columns``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/columns'
        cols = self._jsonize_col_options(cols)
        json = {'columns': cols}
        return self.apicall(url, 'PATCH', json=json)

    @check_safemode
    def add_update_cols(self, table_id: str, cols: list[dict], 
                        noadd: bool = True, noupdate: bool = True, 
                        replaceall: bool = False, doc_id: str = '', 
                        team_id: str = '') -> Apiresp:
        """Implement PUT ``/docs/{docId}/tables/{tableId}/columns``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/columns'
        params = {'noadd': noadd, 'noupdate': noupdate, 'replaceall': replaceall}
        cols = self._jsonize_col_options(cols)
        json = {'columns': cols}
        return self.apicall(url, 'PUT', params=params, json=json)

    @check_safemode
    def delete_column(self, table_id: str, col_id: str, doc_id: str, 
                      team_id: str = '') -> Apiresp:
        """Implement DELETE ``/docs/{docId}/tables/{tableId}/columns/{colId}``.
        
        If successful, response will be ``None``.
        """
        # it's safer to ask for a doc id here
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/columns/{col_id}'
        return self.apicall(url, 'DELETE')

    # DATA
    # ------------------------------------------------------------------

    @check_safemode
    def delete_rows(self, table_id: str, rows: list[int], doc_id: str, 
                    team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/tables/{tableId}/data/delete``.
        
        If successful, response will be ``None``.
        """
        # unclear if deprecated... seems the only way to delete a row though
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/data/delete'
        # this is the *only* api endpoint where "json" is a list, not a dict
        return self.apicall(url, 'POST', json=rows) # type: ignore

    # ATTACHMENTS
    # ------------------------------------------------------------------
 
    def list_attachments(self, filter: dict|None = None, sort: str = '', 
                         limit: int = 0, doc_id: str = '', 
                         team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/attachments``.
        
        If successful, response will be a ``list[dict]`` of attachments.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/attachments'
        params = dict()
        if sort:
            params.update({'sort': sort})
        if limit:
            params.update({'limit': limit})
        if filter:
            # Requests will *form*-encode the filter, Grist want it *url*-encoded
            # instead, so we need to skip Request and manually compose the url
            params.update({'filter': modjson.dumps(filter)})
            encoded_params = urlencode(params, quote_via=quote)
            st, res = self.apicall(url+'?'+encoded_params)
        else:
            # the usual way
            st, res = self.apicall(url, params=params)
        try:
            return st, res['records']
        except KeyError:
            return st, res
        
    @check_safemode
    def upload_attachment(self, filename: str, doc_id: str = '', 
                          team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/attachments``.
        
        If successful, response will be a ``list[int]`` of attachments ids.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/attachments'
        headers = dict()
        return self.apicall(url, 'POST', headers=headers, filename=filename)

    def see_attachment(self, attachment_id: int, doc_id: str = '',
                       team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/attachments/{attachmentId}``.
        
        If successful, response will be a ``dict`` of attachment metadata.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/attachments/{attachment_id}'
        return self.apicall(url)

    def download_attachment(self, filename: str, attachment_id: int, 
                            doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/attachments/{attachmentId}/download``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/attachments/{attachment_id}/download'
        headers = {'accept': '*/*'}
        return self.apicall(url, headers=headers, filename=filename)

    # WEBHOOKS
    # ------------------------------------------------------------------
 
    def list_webhooks(self, doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement ``GET /docs/{docId}/webhooks``.
        
        If successful, response will be a ``list[dict]`` of webhooks.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/webhooks'
        st, res = self.apicall(url)
        try:
            return st, res['webhooks']
        except KeyError:
            return st, res
        
    @check_safemode
    def add_webhooks(self, webhooks: list[dict], doc_id: str = '',
                     team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/webhooks``.
        
        If successful, response will be a ``list[str]`` of added webhook ids.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/webhooks'
        st, res = self.apicall(url, 'POST', json={'webhooks': webhooks})
        try:
            return st, [i['id'] for i in res['webhooks']]
        except KeyError:
            return st, res

    @check_safemode
    def update_webhook(self, webhook_id: str, webhook: dict, 
                       doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}/webhooks/{webhookId}``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/webhooks/{webhook_id}'
        st, res = self.apicall(url, 'PATCH', json=webhook)
        if st <= 200:
            return st, None # Grist api returns "{success: true}" here
        else:
            return st, res

    @check_safemode
    def delete_webhook(self, webhook_id: str, doc_id: str = '', 
                       team_id: str = '') -> Apiresp:
        """Implement DELETE ``/docs/{docId}/webhooks/{webhookId}``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/webhooks/{webhook_id}'
        st, res = self.apicall(url, 'DELETE')
        if st <= 200:
            return st, None # Grist api returns "{success: true}" here
        else:
            return st, res

    @check_safemode
    def empty_payloads_queue(self, doc_id: str = '', 
                             team_id: str = '') -> Apiresp:
        """Implement DELETE ``/docs/{docId}/webhooks/queue``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/webhooks/queue'
        st, res = self.apicall(url, 'DELETE')
        if st <= 200:
            return st, None # Grist api returns "{success: true}" here
        else:
            return st, res

    # SQL
    # ------------------------------------------------------------------
 
    def run_sql(self, sql: str, doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/sql``.
        
        If a converter named "sql" is found, data conversion will be attempted. 
        If successful, response will be a list of "Pygrister records" 
        (see docs) with or without id, depending on the query.  
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/sql'
        params = {'q': sql}
        st, res = self.apicall(url, params=params)
        try:
            records = [r['fields'] for r in res['records']]
        except KeyError:
            return st, res
        try:
            converter = self.out_converter['sql']
        except KeyError: # no converter for this queryset
            return st, records
        return st, self._apply_out_converter(records, converter)

    def run_sql_with_args(self, sql: str, qargs: list, timeout: int = 1000,
                          doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/sql``.
        
        If a converter named "sql" is found, data conversion will be attempted. 
        If successful, response will be a list of "Pygrister records" 
        (see docs) with or without id, depending on the query. 
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/sql'
        json = {'sql': sql, 'args': qargs, 'timeout': timeout}
        st, res = self.apicall(url, method='POST', json=json)
        try:
            records = [r['fields'] for r in res['records']]
        except KeyError:
            return st, res
        try:
            converter = self.out_converter['sql']
        except KeyError: # no converter for this queryset
            return st, records
        return st, self._apply_out_converter(records, converter)
