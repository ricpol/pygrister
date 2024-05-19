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

In addition, Pygrister will not attempt to convert sent and received data types: 
a separate, high-level manager will one day be available for type conversion 
and a slightly friendlier interface. 

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

You should read the documentation first, to learn about the basic Pygrister 
concepts, patterns and configurations. However, the api call functions 
themselves are not documented in Pygrister: see the 
`Grist API reference documentation <https://support.getgrist.com/api/>`_ 
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

from requests import request, JSONDecodeError

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
            msg += f'Configuration:\n{config2output(self.config, True)}'
            raise GristApiInSafeMode(msg)
        return funct(self, *a, **k)
    return wrapper

Apiresp = tuple[int, Any] #: the return type of all api call functions

# TODO everywhere, construct query params so that api defauls are not included
# in the url... problem is, params defaults are not well-documented

class GristApi:
    def __init__(self, config: dict[str, str]|None = None):
        self.reconfig(config)
        self.apicalls: int = 0            #: total number of API calls
        self.req_url: str = ''            #: last request url
        self.req_body: str = ''           #: last request body
        self.req_headers: dict = dict()   #: last request headers
        self.req_method: str = ''         #: last request method
        self.resp_content: str|bytes = '' #: last response content
        self.resp_code: str = ''          #: last response status code
        self.resp_reason: str = ''        #: last response status reason
        self.resp_headers: dict = dict()  #: last reponse headers

    def reconfig(self, config: dict[str, str]|None = None) -> None:
        """Reload the configuration options. 
        
        Call this function if you have just updated config files/env. vars 
        at runtime, and/or pass a dictionary to the ``config`` parameter 
        to override existing config keys for the time being, eg.::

            grist.reconfig({'GRIST_TEAM_SITE': 'newteam'})

        now all future api calls will be directed to the new team site. 
        """
        self.config = get_config()
        if config is not None:
            self.config.update(config)
        if not self.config or not all(self.config.values()):
            msg = f'Missing config values.\n{config2output(self.config)}'
            raise GristApiNotConfigured(msg)
        self.server = self.make_server(self.config['GRIST_SERVER_PROTOCOL'],
                                       self.config['GRIST_TEAM_SITE'],
                                       self.config["GRIST_API_SERVER"])
        self.raise_option = (self.config['GRIST_RAISE_ERROR'] == 'Y')
        self.safemode = (self.config['GRIST_SAFEMODE'] == 'Y')

    def make_server(self, protocol: str = '', subdomain: str = '', 
                    domain: str = '') -> str:
        """Construct a server url from prefix, sub(team)-domain and domain. 
        
        Pass an empty string to any parameter to default to the 
        corresponding configuration key.
        """
        #TODO we need support for custom domains too
        protocol = protocol or self.config['GRIST_SERVER_PROTOCOL']
        subdomain = subdomain or self.config['GRIST_TEAM_SITE']
        domain = domain or self.config['GRIST_API_SERVER']
        return f'{protocol}{subdomain}.{domain}'

    def _select_params(self, doc_id: str = '', team_id: str = ''):
        doc = doc_id or self.config['GRIST_DOC_ID']
        if not team_id:
            server = self.server
        else:
            server = self.make_server(subdomain=team_id)
        return doc, server

    def apicall(self, url: str, method: str = 'GET', headers: dict|None = None, 
                params: dict|None = None, json: dict|None = None, 
                filename: str = '') -> Apiresp:
        self.apicalls += 1
        if headers is None:
            headers = {'Content-Type': 'application/json',
                       'Accept': 'application/json'}
        headers.update(
            {'Authorization': f'Bearer {self.config["GRIST_API_KEY"]}'})

        if not filename:  # ordinary request
            resp = request(method, url, headers=headers, params=params, 
                           json=json) 
            self._save_request_data(resp)
            # TODO the old grist_api.py went to great lengths to retry in case 
            # of an SQLITE_BUSY error. Maybe this is best left to the caller?
            if self.raise_option:
                resp.raise_for_status()
            return resp.status_code, resp.json()
        else:
            if method == 'GET': # download mode
                with request(method, url, headers=headers, params=params, 
                             stream=True) as resp:
                    self._save_request_data(resp)
                    if self.raise_option:
                        resp.raise_for_status()
                    if resp.ok:
                        with open(filename, 'wb') as f:
                            for chunk in resp.iter_content(chunk_size=1024*100):
                                f.write(chunk)
                return resp.status_code, None
            else: # 'POST', upload mode
                # TODO this is ugly... headers and the "upload" bit below  
                # are too coupled with the specific needs of upload_attachment;
                # it *is* the only function that requires this code though!
                # TODO Grist api doesn't support upload streaming, apparently?
                # (i.e., the same as below but with "data={'upload': f}")
                with open(filename, 'rb') as f:
                    resp = request(method, url, headers=headers, 
                                   files={'upload': f})
                self._save_request_data(resp)
                if self.raise_option:
                    resp.raise_for_status()
                return resp.status_code, resp.json()

    def _save_request_data(self, response):
        self.req_url = response.request.url
        self.req_body = response.request.body
        self.req_headers = response.request.headers
        self.req_method = response.request.method
        try:
            self.resp_content = str(response.json())[:MAXSAVEDRESP]
        except JSONDecodeError:
            if SAVEBINARYRESP:
                self.resp_content = response.content[:MAXSAVEDRESP]
            else:
                self.resp_content = '<not a valid json>'
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
        txt += f'->Config: {config2output(self.config)}'
        return txt

    # TEAM SITES (organisations)  # always cross-site allowed, of course
    # ------------------------------------------------------------------

    def list_team_sites(self) -> Apiresp:
        """Implement GET ``/orgs``."""
        url = f'{self.server}/orgs'
        return self.apicall(url)
    
    def see_team(self, team_id: str = '') -> Apiresp:
        """Implement GET ``/orgs/{orgId}``."""
        team_id = team_id or 'current'
        url = f'{self.server}/orgs/{team_id}'
        return self.apicall(url)

    @check_safemode
    def update_team(self, new_name: str, team_id: str = '') -> Apiresp:
        """Implement PATCH ``/orgs/{orgId}``.
        
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
        """Implement PATCH ``/orgs/{orgId}/access``."""
        team_id = team_id or 'current'
        json = {'delta': {'users': users}}
        url = f'{self.server}/orgs/{team_id}/access'
        return self.apicall(url, 'PATCH', json=json)

    # WORKSPACES   # cross-site access always allowed
    # ------------------------------------------------------------------

    def list_workspaces(self, team_id: str = '') -> Apiresp:
        """Implement GET ``/{orgId}/workspaces``."""
        team_id = team_id or 'current'
        url = f'{self.server}/orgs/{team_id}/workspaces'
        return self.apicall(url)

    @check_safemode
    def add_workspace(self, name: str, team_id: str = '') -> Apiresp:
        """Implement POST ``/{orgId}/workspaces``."""
        team_id = team_id or 'current'
        url = f'{self.server}/orgs/{team_id}/workspaces'
        json = {'name': name}
        return self.apicall(url, method='POST', json=json)

    def see_workspace(self, ws_id: int = 0) -> Apiresp: 
        """Implement GET ``/workspaces/{workspaceId}``."""
        ws_id = ws_id or int(self.config['GRIST_WORKSPACE_ID'])
        url = f'{self.server}/workspaces/{ws_id}'
        return self.apicall(url)

    @check_safemode
    def update_workspace(self, new_name: str, ws_id: int = 0) -> Apiresp: 
        """Implement PATCH ``/workspaces/{workspaceId}``."""
        ws_id = ws_id or int(self.config['GRIST_WORKSPACE_ID'])
        url = f'{self.server}/workspaces/{ws_id}'
        json = {'name': new_name}
        return self.apicall(url, method='PATCH', json=json)

    @check_safemode
    def delete_workspace(self, ws_id: int = 0) -> Apiresp:
        """Implement DELETE ``/workspaces/{workspaceId}``."""
        # note: it's safer to ask for a workspace id here
        url = f'{self.server}/workspaces/{ws_id}'
        return self.apicall(url, method='DELETE')

    def list_workspace_users(self, ws_id: int = 0) -> Apiresp:
        """Implement GET ``/workspaces/{workspaceId}/access``.
        
        If successful, response will be a ``list[dict]`` of users.
        """
        ws_id = ws_id or int(self.config['GRIST_WORKSPACE_ID'])
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
        """Implement PATCH ``/workspaces/{workspaceId}/access``."""
        ws_id = ws_id or int(self.config['GRIST_WORKSPACE_ID'])
        json = {'delta': {'users': users}}
        url = f'{self.server}/workspaces/{ws_id}/access'
        return self.apicall(url, 'PATCH', json=json)

    # DOCUMENTS
    # ------------------------------------------------------------------

    @check_safemode
    def add_doc(self, name: str, pinned: bool = False, 
                ws_id: int = 0) -> Apiresp:
        """Implement POST ``/workspaces/{workspaceId}/docs``."""
        ws_id = ws_id or int(self.config['GRIST_WORKSPACE_ID'])
        json = {'name': name, 'isPinned': pinned}
        url = f'{self.server}/workspaces/{ws_id}/docs'
        return self.apicall(url, method='POST', json=json)

    def see_doc(self, doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}``."""
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}'
        return self.apicall(url)

    @check_safemode
    def update_doc(self, new_name: str, pinned: bool = False, 
                   doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}``."""
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}'
        json = {'name': new_name, 'isPinned': pinned}
        return self.apicall(url, method='PATCH', json=json)

    @check_safemode
    def delete_doc(self, doc_id: str, team_id: str = '') -> Apiresp:
        """Implement DELETE ``/docs/{docId}``."""
        # note: it's safer to ask for a doc id here
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}'
        return self.apicall(url, method='DELETE')
        
    @check_safemode
    def move_doc(self, ws_id: int, doc_id: str = '', 
                 team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}/move``."""
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/move'
        json = {'workspace': ws_id}
        return self.apicall(url, method='PATCH', json=json)

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
        """Implement PATCH ``/docs/{docId}/access``."""
        doc_id, server = self._select_params(doc_id, team_id)
        json = {'delta': {'maxInheritedRole': max, 'users': users}}
        url = f'{server}/docs/{doc_id}/access'
        return self.apicall(url, 'PATCH', json=json)

    def download_sqlite(self, filename: str, nohistory: bool = False, 
                        template: bool = False, doc_id: str = '', 
                        team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/download``."""
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/download'
        headers = {'Accept': 'application/x-sqlite3'}
        params = {'nohistory': nohistory, 'template': template}
        return self.apicall(url, headers=headers, params=params, 
                            filename=filename)

    def download_excel(self, filename: str, table_id: str, 
                       header: str = 'label', doc_id: str = '', 
                       team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/download/xlsx``."""
        #TODO: table_id param is actually undocumented and possibly a mistake
        # it should be possible to get the entire db in excel format, via the api?
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/download/xlsx'
        headers = {'Accept': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
        params = {'header': header, 'tableId': table_id}
        return self.apicall(url, headers=headers, params=params, 
                            filename=filename)

    def download_csv(self, filename: str, table_id: str, 
                     header: str = 'label', doc_id: str = '', 
                     team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/download/csv``."""
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

    def list_records(self, table_id: str, filter: dict|None = None, 
                     sort: str = '', limit: int = 0, hidden: bool = False, 
                     doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/tables/{tableId}/records``.
        
        If successful, response will be a ``list[dict]`` of records.
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
            return st, res['records']
        except KeyError:
            return st, res

    @check_safemode
    def add_records(self, table_id: str, records: list[dict], 
                    noparse: bool = False, doc_id: str = '', 
                    team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/tables/{tableId}/records``."""
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/records'
        params = {'noparse': noparse}
        json = {'records': records}
        return self.apicall(url, 'POST', params=params, json=json)

    @check_safemode
    def update_records(self, table_id: str, records: list[dict], 
                       noparse: bool = False, doc_id: str = '', 
                       team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}/tables/{tableId}/records``."""
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/records'
        params = {'noparse': noparse}
        json = {'records': records}
        return self.apicall(url, 'PATCH', params=params, json=json)

    @check_safemode
    def add_update_records(self, table_id: str, records: list[dict], 
                           noparse: bool = False, onmany: str = 'first', 
                           noadd: bool = False, noupdate: bool = False, 
                           allow_empty_require: bool = False, 
                           doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement PUT ``/docs/{docId}/tables/{tableId}/records``."""
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
        """Implement POST ``/docs/{docId}/tables``."""
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables'
        json = {'tables': tables}
        return self.apicall(url, 'POST', json=json)

    @check_safemode
    def update_tables(self, tables: list[dict], doc_id: str = '', 
                      team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}/tables``."""
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
        """Implement POST ``/docs/{docId}/tables/{tableId}/columns``."""
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/columns'
        cols = self._jsonize_col_options(cols)
        json = {'columns': cols}
        return self.apicall(url, 'POST', json=json)

    @check_safemode
    def update_cols(self, table_id: str, cols: list[dict], 
                    doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}/tables/{tableId}/columns``."""
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
        """Implement PUT ``/docs/{docId}/tables/{tableId}/columns``."""
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/columns'
        params = {'noadd': noadd, 'noupdate': noupdate, 'replaceall': replaceall}
        cols = self._jsonize_col_options(cols)
        json = {'columns': cols}
        return self.apicall(url, 'PUT', params=params, json=json)

    @check_safemode
    def delete_column(self, table_id: str, col_id: str, doc_id: str, 
                      team_id: str = '') -> Apiresp:
        """Implement DELETE ``/docs/{docId}/tables/{tableId}/columns/{colId}``."""
        # note: it's safer to ask for a doc id here
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/columns/{col_id}'
        return self.apicall(url, 'DELETE')

    # DATA
    # ------------------------------------------------------------------

    @check_safemode
    def delete_rows(self, table_id: str, rows: list[int], doc_id: str, 
                    team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/tables/{tableId}/data/delete``."""
        # unclear if deprecated... seems the only way to delete a row though
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/data/delete'
        #TODO this is the *only* api endpoint where "json" is a list, not a dict
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
            # Note: filters here work only for attachment properties, 
            # so they are not really useful I'm afraid
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
        """Implement POST ``/docs/{docId}/attachments``."""
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/attachments'
        headers = dict()
        return self.apicall(url, 'POST', headers=headers, filename=filename)

    def see_attachment(self, attachment_id: int, doc_id: str = '',
                       team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/attachments/{attachmentId}``."""
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/attachments/{attachment_id}'
        return self.apicall(url)

    def download_attachment(self, filename: str, attachment_id: int, 
                            doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/attachments/{attachmentId}/download``."""
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
        """Implement POST ``/docs/{docId}/webhooks``."""
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/webhooks'
        return self.apicall(url, 'POST', json={'webhooks': webhooks})

    @check_safemode
    def update_webhook(self, webhook_id: str, webhook: dict, 
                       doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}/webhooks/{webhookId}``."""
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/webhooks/{webhook_id}'
        return self.apicall(url, 'PATCH', json=webhook)

    @check_safemode
    def delete_webhook(self, webhook_id: str, doc_id: str = '', 
                       team_id: str = '') -> Apiresp:
        """Implement DELETE ``/docs/{docId}/webhooks/{webhookId}``."""
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/webhooks/{webhook_id}'
        return self.apicall(url, 'DELETE')

    @check_safemode
    def empty_payloads_queue(self, doc_id: str = '', 
                             team_id: str = '') -> Apiresp:
        """Implement DELETE ``/docs/{docId}/webhooks/queue``."""
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/webhooks/queue'
        return self.apicall(url, 'DELETE')

    # SQL
    # ------------------------------------------------------------------
 
    # note: in the following "run_sql_*" APIs, Grist happily accepts how 
    # Requests *form*-encodes the sql statement in the url... 
    # compare and contrast: the filters in list_attachments and see_records

    def run_sql(self, sql: str, doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/sql``.
        
        If successful, response will be a ``list[dict]`` of records.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/sql'
        params = {'q': sql}
        st, res = self.apicall(url, params=params)
        try:
            return st, res['records']
        except KeyError:
            return st, res

    def run_sql_with_args(self, sql: str, qargs: list, timeout: int = 1000,
                          doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/sql``.
        
        If successful, response will be a ``list[dict]`` of records.
        """
        doc_id, server = self._select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/sql'
        json = {'sql': sql, 'args': qargs, 'timeout': timeout}
        st, res = self.apicall(url, method='POST', json=json)
        try:
            return st, res['records']
        except KeyError:
            return st, res
