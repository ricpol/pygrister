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

import json as modjson # "json" is a common name for request params...
import functools
from pathlib import Path
from urllib.parse import urlencode, quote
from inspect import currentframe, getframeinfo
from warnings import showwarning
from pygrister.apicaller import ApiCaller, Apiresp
from pygrister.config import Configurator
from pygrister.exceptions import *

get_config = Configurator.get_config #: the global, "static" configuration

def check_safemode(funct):
    """If Pygrister is in safemode, no writing API call will pass through."""
    @functools.wraps(funct)
    def wrapper(self, *a, **k):
        if self.configurator.safemode:
            dry_run_status = self.apicaller.dry_run
            self.apicaller.dry_run = True
            try:
                _ = funct(self, *a, **k)
            finally:
                self.apicaller.dry_run = dry_run_status
            msg = 'Pygrister is in safe mode: you cannot write to db.'
            raise GristApiInSafeMode(msg)
        return funct(self, *a, **k)
    return wrapper

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
                 custom_configurator: Configurator|None = None, 
                 custom_apicaller: ApiCaller|None = None):
        """The main Pygrister interface to post Grist API calls.
        
        You may pass any custom data converter ``in_converter`` and 
        ``out_converter`` here. 
        Pass a ``config`` dict to apply runtime changes on top of any "static" 
        configuration (files and env variables) you may have set.
        You may also pass a ``custom_configurator`` or a ``custom_apicaller``, 
        but not both, for advance customisation.
        """
        if custom_apicaller is not None and custom_configurator is not None:
            msg = 'Do not pass both custom apicaller and configurator arguments.'
            raise GristApiNotConfigured(msg)
        if custom_configurator is None:
            self.configurator = Configurator()
        else:
            self.configurator = custom_configurator
        if custom_apicaller is None:
            self.apicaller = ApiCaller(self.configurator)
        else:
            self.apicaller = custom_apicaller
            self.configurator = self.apicaller.configurator
        if config is not None:
            self.configurator.update_config(config)
        self.in_converter = {}            #: converters for input data
        self.out_converter = {}           #: converters for output data
        if in_converter:
            self.in_converter = in_converter
        if out_converter:
            self.out_converter = out_converter

    def reconfig(self, config: dict[str, str]|None = None) -> None:
        """Reload the configuration options. 
        
        A shortcut for ``self.configurator.recongif(config)``.
        """
        return self.configurator.reconfig(config)

    def update_config(self, config: dict[str, str]) -> None:
        """Edit the configuration options.
        
        A shortcut for ``self.configurator.update_config(config)``.
        """
        return self.configurator.update_config(config)

    def make_server(self, team_name: str = '') -> str: #TODO keep it??
        """Construct the "server" part of the API url, up to "/api". 
        
        A shortcut for ``self.configurator.make_server(team_name)``.
        """
        return self.configurator.make_server(team_name)
    
    def open_session(self) -> None:
        """Open a Requests sessions for all subsequent Api calls.
        
        A shortcut for ``self.apicaller.open_session()``."""
        return self.apicaller.open_session()
    
    def close_session(self) -> None:
        """Close an open session, if any.
        
        A shortcut for ``self.apicaller.close_session()``."""
        return self.apicaller.close_session()
    
    @property
    def ok(self) -> bool:
        """``False`` if a HTTP error occurred in the response.
        
        If no response was retrieved, ``ok`` will be ``False`` by default.
        A shortcut for ``self.apicaller.ok``."""
        return self.apicaller.ok

    def inspect(self, sep: str = '\n', max_content: int = 1000) -> str:
        """Collect info on the last api call that was requested (and possibly 
        responded to) by the server. 

        Use ``sep`` to set a custom separator between elements, 
        and ``max_content`` to limit the response content size. 

        A shortcut for ``self.caller.inspect()``."""
        return self.apicaller.inspect(sep, max_content)

    # SERVICE ACCOUNTS
    # ------------------------------------------------------------------

    def list_service_accounts(self) -> Apiresp:
        """Implement GET ``/service-accounts``.
        
        If successful, response will be a ``list[dict]`` of account details.
        """
        url = f'{self.configurator.server}/service-accounts'
        return self.apicaller.apicall(url)
    
    @check_safemode
    def add_service_account(self, expire: str, label: str = '', 
                            description: str = '') -> Apiresp:
        """Implement POST ``/service-accounts``.
        
        If successful, response will be a tuple of service id and key.
        """
        url = f'{self.configurator.server}/service-accounts'
        json = {'expiresAt': expire}
        if label: 
            json['label'] = label
        if description:
            json['description'] = description
        st, res = self.apicaller.apicall(url, method='POST', json=json)
        if self.ok:
            res = (res['id'], res['key'])
        return st, res
    
    def see_service_account(self, service_id: int) -> Apiresp: 
        """Implement GET ``/service-accounts/{saId}``.
        
        If successful, response will be a ``dict`` of service details.
        """
        url = f'{self.configurator.server}/service-accounts/{service_id}'
        return self.apicaller.apicall(url)
    
    @check_safemode
    def update_service_account(self, service_id: int, expire: str = '', 
                               label: str = '', description: str = '') -> Apiresp:
        """Implement PATCH ``/service-accounts/{saId}``.
       
        If successful, response will be ``None``.
        """
        url = f'{self.configurator.server}/service-accounts/{service_id}'
        json = dict()
        if expire:
            json['expiresAt'] = expire
        if label: 
            json['label'] = label
        if description:
            json['description'] = description
        st, res = self.apicaller.apicall(url, method='PATCH', json=json)
        if self.ok:
            res = None
        return st, res
    
    @check_safemode
    def delete_service_account(self, service_id: int) -> Apiresp:
        """Implement DELETE ``/service-accounts/{saId}``.
        
        If successful, response will be ``None``.
        """
        url = f'{self.configurator.server}/service-accounts/{service_id}'
        st, res = self.apicaller.apicall(url, 'DELETE')
        if self.ok:
            res = None
        return st, res
    
    @check_safemode
    def update_service_account_key(self, service_id: int) -> Apiresp:
        """Implement POST ``/service-accounts/{saId}/apikey``.
        
        If successful, response will be the new key as ``str``.
        """
        url = f'{self.configurator.server}/service-accounts/{service_id}/apikey'
        st, res = self.apicaller.apicall(url, 'POST')
        if self.ok:
            return st, res['key']
        return st, res

    @check_safemode
    def delete_service_account_key(self, service_id: int) -> Apiresp:
        """Implement DELETE ``/service-accounts/{saId}/apikey``.
        
        If successful, response will be ``None``.
        """
        url = f'{self.configurator.server}/service-accounts/{service_id}/apikey'
        st, res = self.apicaller.apicall(url, 'DELETE')
        if self.ok:
            res = None
        return st, res

    # USERS (/scim/v2 and /user endpoints)
    # ------------------------------------------------------------------

    def see_user(self, user_id: int) -> Apiresp:
        """Implement GET ``/scim/v2/Users/{userId}``. 
        
        If successful, response will be a ``dict`` of user details. 
        If scim is not enabled, will return Http 501.
        """
        url = f'{self.configurator.server}/scim/v2/Users/{user_id}'
        return self.apicaller.apicall(url, 
                    headers={'Content-Type': 'application/scim+json'})

    def see_myself(self) -> Apiresp:
        """Implement GET ``/scim/v2/Me``. 
        
        If successful, response will be a ``dict`` of logged-in user's details. 
        If scim is not enabled, will return Http 501.
        """
        url = f'{self.configurator.server}/scim/v2/Me'
        return self.apicaller.apicall(url,
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
        url = f'{self.configurator.server}/scim/v2/Users'
        headers = {'Content-Type': 'application/scim+json'}
        if filter:
            # Requests will *form*-encode the filter, Grist want it *url*-encoded
            # instead, so we need to skip Request and manually compose the url
            params = {'startIndex': start, 'count': chunk, 
                      'filter': modjson.dumps(filter)}
            encoded_params = urlencode(params, quote_via=quote)
            st, res = self.apicaller.apicall(url+'?'+encoded_params, 
                                          headers=headers)
        else:
            # the usual way
            st, res = self.apicaller.apicall(url, headers=headers, 
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
        ``['urn:ietf:params:scim:schemas:core:2.0:User']``

        If successful, response will be the user id as an ``int``. 
        If scim is not enabled, will return Http 501.
        """
        json = self._make_user_data(username, emails, formatted_name, 
                                    display_name,lang, locale, photos, schemas)
        url = f'{self.configurator.server}/scim/v2/Users'
        st, res = self.apicaller.apicall(url, 'POST', json=json, 
                        headers={'Content-Type': 'application/scim+json'})
        if self.ok:
            return st, int(res['id'])
        else:
            return st, res

    @check_safemode
    def update_user_override(self, user_id: int, username: str, emails: list[str],
                             formatted_name: str = '', display_name: str = '', 
                             lang: str = 'en', locale: str = 'en', 
                             photos: list[str]|None = None, 
                             schemas: list[str]|None = None) -> Apiresp:
        """Implement PUT ``/scim/v2/Users/{userId}``. 
        
        Note: ``schemas`` defaults to 
        ``['urn:ietf:params:scim:schemas:core:2.0:User']``

        If successful, response will be ``None``. 
        If scim is not enabled, will return Http 501.
        """
        json = self._make_user_data(username, emails, formatted_name, 
                                    display_name,lang, locale, photos, schemas)
        url = f'{self.configurator.server}/scim/v2/Users/{user_id}'
        st, res = self.apicaller.apicall(url, 'PUT', json=json, 
                        headers={'Content-Type': 'application/scim+json'})
        if self.ok:
            return st, None
        else:
            return st, res

    @check_safemode
    def update_user(self, user_id: int, operations: list[dict], 
                    schemas: list[str]|None = None) -> Apiresp:
        """Implement PATCH ``/scim/v2/Users/{userId}``. 
        
        Note: ``schemas`` defaults to 
        ``['urn:ietf:params:scim:api:messages:2.0:PatchOp']``

        If successful, response will be ``None``. 
        If scim is not enabled, will return Http 501.
        """
        if schemas is None:
            schemas = ['urn:ietf:params:scim:api:messages:2.0:PatchOp']
        json = {'Operations': operations, 'schemas': schemas}
        url = f'{self.configurator.server}/scim/v2/Users/{user_id}'
        st, res = self.apicaller.apicall(url, 'PATCH', json=json, 
                        headers={'Content-Type': 'application/scim+json'})
        if self.ok:
            return st, None
        else:
            return st, res
    
    @check_safemode
    def enable_user(self, user_id: int, enable: bool = True):
        """Implement POST ``/users/{userId}/enable`` and 
        POST ``/users/{userId}/disable`` (accessible to admins only). 
        
        If successful, response will be ``None``.
        """
        operation = 'enable' if enable else 'disable'
        url = f'{self.configurator.server}/users/{user_id}/{operation}'
        return self.apicaller.apicall(url, 'POST')

    @check_safemode
    def delete_user(self, user_id: int):
        """Implement DELETE ``/scim/v2/Users/{userId}``. 
        
        If successful, response will be ``None``. 
        If scim is not enabled, will return Http 501.
        """
        url = f'{self.configurator.server}/scim/v2/Users/{user_id}'
        st, res = self.apicaller.apicall(url, 'DELETE', 
                    headers={'Content-Type': 'application/scim+json'})
        if self.ok:
            res = None
        return st, res

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
        # doc_id, server = self.configurator.select_params(doc_id, team_id)
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
        ``['urn:ietf:params:scim:api:messages:2.0:BulkRequest']``

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
        ``['urn:ietf:params:scim:api:messages:2.0:BulkRequest']``

        If successful, response will be a ``dict`` of user data. 
        If scim is not enabled, will return Http 501. 
        """
        url = f'{self.configurator.server}/scim/v2/Users/.search'
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
        return self.apicaller.apicall(url, 'POST', headers=headers, json=json)

    @check_safemode
    def bulk_users(self, operations: list[dict], 
                   schemas: list[str]|None = None) -> Apiresp:
        """Implement POST ``/scim/v2/Bulk``. 

        Note: ``schemas`` defaults to 
        ``['urn:ietf:params:scim:api:messages:2.0:BulkRequest']``

        If successful, response will be a ``list[int]`` of status codes for 
        each operation (inspect ``GristApi.resp_content`` for details, 
        if any operations resulted in a bad status code).
        If scim is not enabled, will return Http 501.
        """
        if schemas is None:
            schemas = ['urn:ietf:params:scim:api:messages:2.0:BulkRequest']
        json = {'Operations': operations, 'schemas': schemas}
        url = f'{self.configurator.server}/scim/v2/Bulk'
        st, res = self.apicaller.apicall(url, 'POST', json=json, 
                        headers={'Content-Type': 'application/scim+json'})
        if self.ok:
            return st, [int(i['status']) for i in res['Operations']]
        else:
            return st, res

    def see_scim_schemas(self) -> Apiresp:
        """Implement GET ``/scim/v2/Schemas``. 
        
        If successful, response will a ``dict`` of scim schemas. 
        If scim is not enabled, will return Http 501.
        """
        url = f'{self.configurator.server}/scim/v2/Schemas'
        return self.apicaller.apicall(url, 
                    headers={'Content-Type': 'application/scim+json'})

    def see_scim_config(self) -> Apiresp:
        """Implement GET ``/scim/v2/ServiceProviderConfig``. 
        
        If successful, response will a ``dict`` of scim provider configuration. 
        If scim is not enabled, will return Http 501.
        """
        url = f'{self.configurator.server}/scim/v2/ServiceProviderConfig'
        return self.apicaller.apicall(url, 
                    headers={'Content-Type': 'application/scim+json'})

    def see_scim_resources(self) -> Apiresp:
        """Implement GET ``/scim/v2/ResourceTypes``. 
        
        If successful, response will a ``dict`` of scim resources. 
        If scim is not enabled, will return Http 501.
        """
        url = f'{self.configurator.server}/scim/v2/ResourceTypes'
        return self.apicaller.apicall(url, 
                    headers={'Content-Type': 'application/scim+json'})

    # TEAM SITES (organisations)
    # ------------------------------------------------------------------

    def list_team_sites(self) -> Apiresp:
        """Implement GET ``/orgs``.
        
        If successful, response will be a ``list[dict]`` of site details.
        """
        url = f'{self.configurator.server}/orgs'
        return self.apicaller.apicall(url)
    
    def see_team(self, team_id: str = '') -> Apiresp:
        """Implement GET ``/orgs/{orgId}``.
        
        If successful, response will be a ``dict`` of site details.
        """
        team_id = team_id or 'current'
        url = f'{self.configurator.server}/orgs/{team_id}'
        return self.apicaller.apicall(url)

    def see_team_usage(self, team_id: str = '') -> Apiresp:
        """Implement GET ``/orgs/{orgId}/usage``.
        
        If successful, response will be a ``dict`` of usage details.
        """
        team_id = team_id or 'current'
        url = f'{self.configurator.server}/orgs/{team_id}/usage'
        return self.apicaller.apicall(url)

    @check_safemode
    def update_team(self, new_name: str, team_id: str = '') -> Apiresp:
        """Implement PATCH ``/orgs/{orgId}``.
       
        If successful, response will be ``None``.
        Note that renaming a team will *not* change the subdomain too!
        """
        team_id = team_id or 'current'
        url = f'{self.configurator.server}/orgs/{team_id}'
        json = {'name': new_name}
        return self.apicaller.apicall(url, method='PATCH', json=json)

    @check_safemode
    def delete_team_old(self, team_id: str = '') -> Apiresp:
        """Implement DELETE ``/orgs/{orgId}``.
        
        If successful, response will be ``None``.
        Note: disabled in Grist 1.7.4, will return Http 410 instead.
        """
        team_id = team_id or 'current'
        url = f'{self.configurator.server}/orgs/{team_id}'
        st, res = self.apicaller.apicall(url, 'DELETE')
        if self.ok:
            res = None
        return st, res

    @check_safemode
    def delete_team(self, team_id: str = '') -> Apiresp:
        """Implement DELETE ``/orgs/{orgId}/{name}``.
        
        If successful, response will be ``None``.
        """
        team_id = team_id or self.configurator.config['GRIST_TEAM_SITE']
        # the {name} part can be the team name again, or just "force-delete"
        url = f'{self.configurator.server}/orgs/{team_id}/force-delete'
        st, res = self.apicaller.apicall(url, 'DELETE')
        if self.ok:
            res = None
        return st, res

    def list_team_users(self, team_id: str = '') -> Apiresp:
        """Implement GET ``/orgs/{orgId}/access``.
        
        If successful, response will be a ``list[dict]`` of users.
        """
        team_id = team_id or 'current'
        url = f'{self.configurator.server}/orgs/{team_id}/access'
        st, res = self.apicaller.apicall(url)
        if self.ok:
            return st, res['users']
        else:
            return st, res

    @check_safemode
    def update_team_users(self, users: dict[str, str], 
                          team_id: str = '') -> Apiresp:
        """Implement PATCH ``/orgs/{orgId}/access``.
        
        If successful, response will be ``None``.
        """
        team_id = team_id or 'current'
        json = {'delta': {'users': users}}
        url = f'{self.configurator.server}/orgs/{team_id}/access'
        return self.apicaller.apicall(url, 'PATCH', json=json)

    # WORKSPACES
    # ------------------------------------------------------------------

    def list_workspaces(self, team_id: str = '') -> Apiresp:
        """Implement GET ``/{orgId}/workspaces``.
        
        If successful, response will be a ``list[dict]`` of workspaces.
        """
        team_id = team_id or 'current'
        url = f'{self.configurator.server}/orgs/{team_id}/workspaces'
        return self.apicaller.apicall(url)

    @check_safemode
    def add_workspace(self, name: str, team_id: str = '') -> Apiresp:
        """Implement POST ``/{orgId}/workspaces``.
        
        If successful, response will be the workspace id as an ``int``.
        """
        team_id = team_id or 'current'
        url = f'{self.configurator.server}/orgs/{team_id}/workspaces'
        json = {'name': name}
        return self.apicaller.apicall(url, method='POST', json=json)

    def see_workspace(self, ws_id: int = 0) -> Apiresp: 
        """Implement GET ``/workspaces/{workspaceId}``.
        
        If successful, response will be a ``dict`` of workspace details.
        """
        ws_id = ws_id or int(self.configurator.config['GRIST_WORKSPACE_ID'])
        url = f'{self.configurator.server}/workspaces/{ws_id}'
        return self.apicaller.apicall(url)

    @check_safemode
    def update_workspace(self, new_name: str, ws_id: int = 0) -> Apiresp: 
        """Implement PATCH ``/workspaces/{workspaceId}``.
        
        If successful, response will be ``None``.
        """
        ws_id = ws_id or int(self.configurator.config['GRIST_WORKSPACE_ID'])
        url = f'{self.configurator.server}/workspaces/{ws_id}'
        json = {'name': new_name}
        st, res = self.apicaller.apicall(url, method='PATCH', json=json)
        if self.ok and res == ws_id:
            res = None
        return st, res

    @check_safemode
    def delete_workspace(self, ws_id: int = 0) -> Apiresp:
        """Implement DELETE ``/workspaces/{workspaceId}``.
        
        If successful, response will be ``None``.
        """
        ws_id = ws_id or int(self.configurator.config['GRIST_WORKSPACE_ID'])
        url = f'{self.configurator.server}/workspaces/{ws_id}'
        st, res = self.apicaller.apicall(url, method='DELETE')
        if self.ok and res == ws_id:
            res = None
        return st, res

    @check_safemode
    def trash_workspace(self, remove: bool = True, permanent: bool = False, 
                        ws_id: int = 0) -> Apiresp: 
        """Implement POST ``/workspaces/{workspaceId}/remove`` and 
        POST ``/workspaces/{workspaceId}/unremove``. 

        If ``remove`` and ``permanent``, ws will be deleted instead. 
        If ``remove=False``, ``permanent`` is ignored and ws will be recovered.
        
        If successful, response will be ``None``.
        """
        ws_id = ws_id or int(self.configurator.config['GRIST_WORKSPACE_ID'])
        if remove:
            url = f'{self.configurator.server}/workspaces/{ws_id}/remove'
            params = {'permanent': permanent}
        else:
            url = f'{self.configurator.server}/workspaces/{ws_id}/unremove'
            params = dict()
        st, res = self.apicaller.apicall(url, method='POST', params=params)
        if self.ok:
            res = None
        return st, res

    def list_workspace_users(self, ws_id: int = 0) -> Apiresp:
        """Implement GET ``/workspaces/{workspaceId}/access``.
        
        If successful, response will be a ``list[dict]`` of users.
        """
        ws_id = ws_id or int(self.configurator.config['GRIST_WORKSPACE_ID'])
        url = f'{self.configurator.server}/workspaces/{ws_id}/access'
        st, res = self.apicaller.apicall(url)
        if self.ok:
            # note: we leave out the 'maxInheritedRole' information here!
            return st, res['users']
        else:
            return st, res

    @check_safemode
    def update_workspace_users(self, users: dict[str, str], 
                               ws_id: int = 0) -> Apiresp:
        """Implement PATCH ``/workspaces/{workspaceId}/access``.
        
        If successful, response will be ``None``.
        """
        ws_id = ws_id or int(self.configurator.config['GRIST_WORKSPACE_ID'])
        json = {'delta': {'users': users}}
        url = f'{self.configurator.server}/workspaces/{ws_id}/access'
        return self.apicaller.apicall(url, 'PATCH', json=json)

    # DOCUMENTS
    # ------------------------------------------------------------------

    @check_safemode
    def add_doc(self, name: str, pinned: bool = False, 
                ws_id: int = 0) -> Apiresp:
        """Implement POST ``/workspaces/{workspaceId}/docs``.
        
        If successful, response will be the doc id as a ``str``.
        """
        ws_id = ws_id or int(self.configurator.config['GRIST_WORKSPACE_ID'])
        json = {'name': name, 'isPinned': pinned}
        url = f'{self.configurator.server}/workspaces/{ws_id}/docs'
        return self.apicaller.apicall(url, method='POST', json=json)

    def see_doc(self, doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}``.
        
        If successful, response will be a ``dict`` of doc details.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}'
        return self.apicaller.apicall(url)

    @check_safemode
    def update_doc(self, new_name: str = '', pinned: bool = False, 
                   doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}'
        json = {'isPinned': pinned}
        if new_name:
            json.update({'name': new_name}) # type:ignore
        st, res = self.apicaller.apicall(url, method='PATCH', json=json)
        if self.ok and res == doc_id:
            res = None
        return st, res

    @check_safemode
    def delete_doc(self, doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement DELETE ``/docs/{docId}``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}'
        st, res = self.apicaller.apicall(url, method='DELETE')
        if self.ok and res == doc_id:
            res = None
        return st, res

    @check_safemode
    def trash_doc(self, remove: bool = True, permanent: bool = False, 
                  doc_id: str = '', team_id: str = '') -> Apiresp: 
        """Implement POST ``/docs/{docId}/remove`` and 
        POST ``/docs/{docId}/unremove``. 

        If ``remove`` and ``permanent``, doc will be deleted instead. 
        If ``remove=False``, ``permanent`` is ignored and doc will be recovered.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        if remove:
            url = f'{server}/docs/{doc_id}/remove'
            params = {'permanent': permanent}
        else:
            url = f'{server}/docs/{doc_id}/unremove'
            params = dict()
        st, res = self.apicaller.apicall(url, method='POST', params=params)
        if self.ok:
            res = None
        return st, res

    @check_safemode
    def delete_doc_history(self, keep: int = 0, 
                           doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/states/remove``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/states/remove'
        json = {'keep': keep}
        return self.apicaller.apicall(url, method='POST', json=json)

    @check_safemode
    def move_doc(self, ws_id: int, doc_id: str = '', 
                 team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}/move``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/move'
        json = {'workspace': ws_id}
        st, res = self.apicaller.apicall(url, method='PATCH', json=json)
        if self.ok and res == doc_id:
            res = None
        return st, res

    @check_safemode
    def copy_doc(self, target_ws: int, target_name: str, template: bool = False, 
                 doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/copy``.
        
        If successful, response will be the ``str`` id of the copied doc.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/copy'
        json = {'workspaceId': target_ws, 'documentName': target_name, 
                'asTemplate': template}
        return self.apicaller.apicall(url, method='POST', json=json)

    @check_safemode
    def reload_doc(self, doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/force-reload``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/force-reload'
        return self.apicaller.apicall(url, method='POST')

    @check_safemode
    def enable_doc(self, enable: bool = True, 
                   doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/enable`` and 
        POST ``/docs/{docId}/disable`` (accessible to admins only). 
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        operation = 'enable' if enable else 'disable'
        url = f'{server}/docs/{doc_id}/{operation}'
        return self.apicaller.apicall(url, 'POST')

    @check_safemode
    def pin_doc(self, pin: bool = True, 
                doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}/pin`` and 
        PATCH ``/docs/{docId}/unpin``. 
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        operation = 'pin' if pin else 'unpin'
        url = f'{server}/docs/{doc_id}/{operation}'
        return self.apicaller.apicall(url, 'PATCH')

    @check_safemode
    def set_recovery_mode(self, mode: bool = True, 
                          doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/recover``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/recover'
        json = {'recoveryMode': mode}
        st, res = self.apicaller.apicall(url, method='POST', json=json)
        if self.ok:
            res = None
        return st, res  

    def list_doc_users(self, doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/access``.
        
        If successful, response will be a ``list[dict]`` of users.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/access'
        st, res = self.apicaller.apicall(url)
        if self.ok:
            # note: we leave out the 'maxInheritedRole' information here!
            return st, res['users']
        else:
            return st, res

    @check_safemode
    def update_doc_users(self, users: dict[str, str], max: str = 'owners', 
                         doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}/access``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        json = {'delta': {'maxInheritedRole': max, 'users': users}}
        url = f'{server}/docs/{doc_id}/access'
        return self.apicaller.apicall(url, 'PATCH', json=json)

    def download_sqlite(self, filename: Path, nohistory: bool = False, 
                        template: bool = False, doc_id: str = '', 
                        team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/download``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/download'
        headers = {'Accept': 'application/x-sqlite3'}
        params = {'nohistory': nohistory, 'template': template}
        return self.apicaller.apicall(url, headers=headers, params=params, 
                                   filename=filename)

    @check_safemode
    def upload_sqlite(self, filename: Path, target_docname: str, 
                      ws_id: int = 0) -> Apiresp:
        """Implement POST ``/workspaces/{workspaceId}/import``.
        
        If successful, response will be the imported doc Id as ``str``.
        """
        ws_id = ws_id or int(self.configurator.config['GRIST_WORKSPACE_ID'])
        url = f'{self.configurator.server}/workspaces/{ws_id}/import'
        headers = dict()
        self.apicaller.request = None  # we must reset here, in case opening 
        self.apicaller.response = None # files throws an exception now:
        f = open(filename, 'rb')
        fileobj = {'upload': f,
                   'documentName': (None, target_docname)}
        try:
            st, res = self.apicaller.apicall(url, 'POST', headers=headers, 
                                             upload_files=fileobj)
        finally:
            f.close()
        if self.ok:
            res = res['id']
        return st, res

    def download_excel(self, filename: Path, table_id: str, 
                       header: str = 'label', doc_id: str = '', 
                       team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/download/xlsx``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/download/xlsx'
        headers = {'Accept': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
        params = {'header': header, 'tableId': table_id}
        return self.apicaller.apicall(url, headers=headers, params=params, 
                                   filename=filename)

    def download_csv(self, filename: Path, table_id: str, 
                     header: str = 'label', doc_id: str = '', 
                     team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/download/csv``.
        
        If successful, response will be ``None``.
        """
        # note: the grist api also puts the data in the response body...
        # we just download the file and return None instead
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/download/csv'
        headers = {'Accept': 'text/csv'}
        params = {'header': header, 'tableId': table_id}
        return self.apicaller.apicall(url, headers=headers, params=params, 
                                   filename=filename)

    def download_schema(self, table_id: str, header: str = 'label',
                        filename: Path|None = None, doc_id: str = '', 
                        team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/download/table-schema``.
        
        If successful, schema will be returned as json; pass the `filename` 
        param to have it downloaded as a json file instead.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        params = {'tableId': table_id, 'header': header}
        url = f'{server}/docs/{doc_id}/download/table-schema'
        headers = {'Accept': 'text/csv'}
        return self.apicaller.apicall(url, headers=headers, params=params, 
                                   filename=filename)

    # RECORDS
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_out_converter(records: list[dict], converter: dict) -> list[dict]:
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
                            is_add_update: bool = False) -> list[dict]:
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
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/records'
        headers = {'X-Sort': sort, 'X-Limit': str(limit)}
        if filter:
            # Requests will *form*-encode the filter, Grist want it *url*-encoded
            # instead, so we need to skip Request and manually compose the url
            params = {'hidden': hidden, 'filter': modjson.dumps(filter)}
            encoded_params = urlencode(params, quote_via=quote)
            st, res = self.apicaller.apicall(url+'?'+encoded_params, 
                                          headers=headers)
        else:
            # the usual way
            st, res = self.apicaller.apicall(url, headers=headers, 
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
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/records'
        params = {'noparse': noparse}
        json = {'records': [{'fields': r} for r in records]}
        st, res = self.apicaller.apicall(url, 'POST', params=params, json=json)
        if self.ok:
            return st, [i['id'] for i in res['records']]
        else:
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
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/records'
        params = {'noparse': noparse}
        json = {'records': [{'id': rec.pop('id'), 'fields': rec} 
                            for rec in records]}
        return self.apicaller.apicall(url, 'PATCH', params=params, json=json)

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
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/records'
        params = {'noparse': noparse, 'onmany': onmany, 'noadd': noadd, 
                  'noupdate': noupdate, 'allow_empty_require': allow_empty_require}
        json = {'records': records}
        return self.apicaller.apicall(url, 'PUT', params=params, json=json)

    # TABLES
    # ------------------------------------------------------------------

    def list_tables(self, doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/tables``.
        
        If successful, response will be a ``list[dict]`` of tables.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables'
        st, res = self.apicaller.apicall(url)
        if self.ok:
            return st, res['tables']
        else:
            return st, res
    
    @check_safemode
    def add_tables(self, tables: list[dict], doc_id: str = '', 
                   team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/tables``.
        
        If successful, response will be a ``list[str]`` of added table ids.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables'
        json = {'tables': tables}
        st, res = self.apicaller.apicall(url, 'POST', json=json)
        if self.ok:
            return st, [i['id'] for i in res['tables']]
        else:
            return st, res
        
    @check_safemode
    def update_tables(self, tables: list[dict], doc_id: str = '', 
                      team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}/tables``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables'
        json = {'tables': tables}
        return self.apicaller.apicall(url, 'PATCH', json=json)

    # COLUMNS
    # ------------------------------------------------------------------

    def list_cols(self, table_id: str, hidden: bool = False, 
                  doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/tables/{tableId}/columns``.
        
        If successful, response will be a ``list[dict]`` of columns.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/columns'
        params = {'hidden': hidden}
        st, res = self.apicaller.apicall(url, params=params)
        if self.ok:
            return st, res['columns']
        else:
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
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/columns'
        cols = self._jsonize_col_options(cols)
        json = {'columns': cols}
        st, res = self.apicaller.apicall(url, 'POST', json=json)
        if self.ok:
            return st, [i['id'] for i in res['columns']]
        else:
            return st, res

    @check_safemode
    def update_cols(self, table_id: str, cols: list[dict], 
                    doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}/tables/{tableId}/columns``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/columns'
        cols = self._jsonize_col_options(cols)
        json = {'columns': cols}
        return self.apicaller.apicall(url, 'PATCH', json=json)

    @check_safemode
    def add_update_cols(self, table_id: str, cols: list[dict], 
                        noadd: bool = True, noupdate: bool = True, 
                        replaceall: bool = False, doc_id: str = '', 
                        team_id: str = '') -> Apiresp:
        """Implement PUT ``/docs/{docId}/tables/{tableId}/columns``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/columns'
        params = {'noadd': noadd, 'noupdate': noupdate, 'replaceall': replaceall}
        cols = self._jsonize_col_options(cols)
        json = {'columns': cols}
        return self.apicaller.apicall(url, 'PUT', params=params, json=json)

    @check_safemode
    def delete_column(self, table_id: str, col_id: str, doc_id: str = '', 
                      team_id: str = '') -> Apiresp:
        """Implement DELETE ``/docs/{docId}/tables/{tableId}/columns/{colId}``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/columns/{col_id}'
        return self.apicaller.apicall(url, 'DELETE')

    # DATA
    # ------------------------------------------------------------------

    @check_safemode
    def delete_rows(self, table_id: str, rows: list[int], doc_id: str = '', 
                    team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/tables/{tableId}/data/delete``.
        
        If successful, response will be ``None``.
        """
        #TODO this is deprecated in Grist 1.7.5, for records/delete
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/tables/{table_id}/data/delete'
        # this is the *only* api endpoint where "json" is a list, not a dict
        return self.apicaller.apicall(url, 'POST', json=rows) # type: ignore

    # ATTACHMENTS
    # ------------------------------------------------------------------
 
    def list_attachments(self, filter: dict|None = None, sort: str = '', 
                         limit: int = 0, doc_id: str = '', 
                         team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/attachments``.
        
        If successful, response will be a ``list[dict]`` of attachments.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
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
            st, res = self.apicaller.apicall(url+'?'+encoded_params)
        else:
            # the usual way
            st, res = self.apicaller.apicall(url, params=params)
        if self.ok:
            return st, res['records']
        else:
            return st, res

    @check_safemode
    def upload_attachment(self, filename: Path, 
                          doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/attachments`` for one file only.
        
        This is *deprecated* and redirects to ``upload_attachments`` 
        which you should use instead.
        """
        line = getframeinfo(currentframe()).lineno + 1 # type: ignore
        showwarning('Use upload_attachments instead', DeprecationWarning, 
                    'api.py', line)
        return self.upload_attachments([filename], doc_id, team_id)
    
    @check_safemode
    def upload_attachments(self, filenames: list[Path], doc_id: str = '', 
                           team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/attachments``.
        
        If successful, response will be a ``list[int]`` of attachments ids.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/attachments'
        headers = dict()
        self.apicaller.request = None  # we must reset here, in case opening 
        self.apicaller.response = None # files throws an exception now:
        fileobjs = [('upload', (str(f), open(f, 'rb'))) for f in filenames]
        try:
            st, res = self.apicaller.apicall(url, 'POST', headers=headers, 
                                          upload_files=fileobjs)
        finally:
            for obj in fileobjs:
                obj[1][1].close()
        return st, res

    @check_safemode
    def upload_restore_attachments(self, filename: Path, 
                                   doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/attachments/archive``.
        
        ``filename``: must be a *tar* file.
        If successful, response will be a summary ``dict`` of attachments used.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/attachments/archive'
        headers = {'Accept': 'application/json'
                   #'Content-Type': 'multipart/form-data', # do not use,
                  }   # or Requests won't add boundaries and Grist will complain
        self.apicaller.request = None  # we must reset here, in case opening 
        self.apicaller.response = None # files throws an exception now:
        with open(filename, 'rb') as f:
            fileobj = [('file', (str(filename), f, 'application/x-tar'))]
            st, res = self.apicaller.apicall(url, method='POST', headers=headers, 
                                          upload_files=fileobj) 
        return st, res

    def see_attachment(self, attachment_id: int, doc_id: str = '',
                       team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/attachments/{attachmentId}``.
        
        If successful, response will be a ``dict`` of attachment metadata.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/attachments/{attachment_id}'
        return self.apicaller.apicall(url)

    def download_attachment(self, filename: Path, attachment_id: int, 
                            doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/attachments/{attachmentId}/download``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/attachments/{attachment_id}/download'
        headers = {'accept': '*/*'}
        return self.apicaller.apicall(url, headers=headers, filename=filename)
    
    def download_attachments(self, filename: Path|None = None, format: str = 'tar', 
                             doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/attachments/archive``.
        
        ``filename``: must be a file name matching with ``format`` 
        and defaults to ``doc_<doc_id>_attachments.<format>``. 
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/attachments/archive'
        headers = {'accept': '*/*'}
        params = {'format': format}
        if filename is None:
            filename = Path(f'doc_{doc_id}_attachments.{format}') 
        return self.apicaller.apicall(url, headers=headers, params=params, 
                                   filename=filename)

    @check_safemode
    def delete_unused_attachments(self, expired_only: bool = False, 
                                  doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/attachments/removeUnused``.

        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/attachments/removeUnused'
        params = {'expiredOnly': expired_only}
        return self.apicaller.apicall(url, method='POST', params=params)

    def see_attachment_store(self, 
                             doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/attachments/store``.
        
        If successful, response will be either ``external`` or ``internal``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/attachments/store'
        st, res = self.apicaller.apicall(url)
        if self.ok:
            return st, res['type']
        else:
            return st, res

    def update_attachment_store(self, internal_store: bool = True, 
                                doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/attachments/store``.
        
        Pass ``internal_store=True`` to set internal storage, ``False`` to set  
        external storage.
        If successful, response will be ``None``.
        Passing ``False`` will return Http 400 if external storage is not 
        configured.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/attachments/store'
        json = {'type': {True:'internal', False:'external'}[internal_store]}
        st, res = self.apicaller.apicall(url, 'POST', json=json)
        if self.ok:
            res = None
        return st, res
  
    def list_store_settings(self, 
                            doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/attachments/stores``.
        
        If successful, response will be a ``list`` of external storage settings.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/attachments/stores'
        st, res = self.apicaller.apicall(url)
        if self.ok:
            return st, res['stores']
        else:
            return st, res

    def transfer_attachments(self,  
                             doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/attachments/transferAll``.

        If successful, response will be a ``dict`` of transfer details.
        If external storage is not configured, will return Http 404.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/attachments/transferAll'
        return self.apicaller.apicall(url, 'POST')

    def see_transfer_status(self,  
                            doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/attachments/transferStatus``.

        If successful, response will be a ``dict`` of transfer details.
        If external storage is not configured, will return Http 404.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/attachments/transferStatus'
        return self.apicaller.apicall(url)

    # WEBHOOKS
    # ------------------------------------------------------------------
 
    def list_webhooks(self, doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement ``GET /docs/{docId}/webhooks``.
        
        If successful, response will be a ``list[dict]`` of webhooks.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/webhooks'
        st, res = self.apicaller.apicall(url)
        if self.ok:
            return st, res['webhooks']
        else:
            return st, res
        
    @check_safemode
    def add_webhooks(self, webhooks: list[dict], doc_id: str = '',
                     team_id: str = '') -> Apiresp:
        """Implement POST ``/docs/{docId}/webhooks``.
        
        If successful, response will be a ``list[str]`` of added webhook ids.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/webhooks'
        st, res = self.apicaller.apicall(url, 'POST', json={'webhooks': webhooks})
        if self.ok:
            return st, [i['id'] for i in res['webhooks']]
        else:
            return st, res

    @check_safemode
    def update_webhook(self, webhook_id: str, webhook: dict, 
                       doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement PATCH ``/docs/{docId}/webhooks/{webhookId}``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/webhooks/{webhook_id}'
        st, res = self.apicaller.apicall(url, 'PATCH', json=webhook)
        if self.ok:
            res = None # Grist api returns "{success: true}" here
        return st, res

    @check_safemode
    def delete_webhook(self, webhook_id: str, doc_id: str = '', 
                       team_id: str = '') -> Apiresp:
        """Implement DELETE ``/docs/{docId}/webhooks/{webhookId}``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/webhooks/{webhook_id}'
        st, res = self.apicaller.apicall(url, 'DELETE')
        if self.ok:
            res = None # Grist api returns "{success: true}" here
        return st, res

    @check_safemode
    def empty_payloads_queue(self, doc_id: str = '', 
                             team_id: str = '') -> Apiresp:
        """Implement DELETE ``/docs/{docId}/webhooks/queue``.
        
        If successful, response will be ``None``.
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/webhooks/queue'
        st, res = self.apicaller.apicall(url, 'DELETE')
        if self.ok:
            res = None # Grist api returns "{success: true}" here
        return st, res

    # SQL
    # ------------------------------------------------------------------
 
    def run_sql(self, sql: str, doc_id: str = '', team_id: str = '') -> Apiresp:
        """Implement GET ``/docs/{docId}/sql``.
        
        If a converter named "sql" is found, data conversion will be attempted. 
        If successful, response will be a list of "Pygrister records" 
        (see docs) with or without id, depending on the query.  
        """
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/sql'
        params = {'q': sql}
        st, res = self.apicaller.apicall(url, params=params)
        if self.ok:
            records = [r['fields'] for r in res['records']]
        else:
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
        doc_id, server = self.configurator.select_params(doc_id, team_id)
        url = f'{server}/docs/{doc_id}/sql'
        json = {'sql': sql, 'args': qargs, 'timeout': timeout}
        st, res = self.apicaller.apicall(url, method='POST', json=json)
        if self.ok:
            records = [r['fields'] for r in res['records']]
        else:
            return st, res
        try:
            converter = self.out_converter['sql']
        except KeyError: # no converter for this queryset
            return st, records
        return st, self._apply_out_converter(records, converter)
