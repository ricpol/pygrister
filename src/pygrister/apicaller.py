from pathlib import Path
from typing import Any
#TODO remove unused imports from Requests
from requests import (request, Request, PreparedRequest, 
                      Response, Session, JSONDecodeError)

from pygrister.config import Configurator, apikey2output

Apiresp = tuple[int, Any] #: the return type of all api call functions

class ApiCaller:
    """The engine for posting a call to the Grist Apis."""
    def __init__(self, 
                 configurator: Configurator,
                 request_options: dict|None = None,
                 ) -> None:
        self.configurator = configurator
        self.session = None           #: Requests session object, or None
        self.request_options = dict() #: other options to pass to Requests
        if request_options:
            self.request_options = request_options
        self.apicalls: int = 0        #: total number of API calls
        self.ok: bool = True          #: if an HTTPError occurred
        self.dry_run: bool = False    #: prepare, do not post request
        self.request: PreparedRequest|None = None #: last request posted
        self.response: Response|None = None       #: last response retrieved

    def open_session(self) -> None:
        """Open a Requests sessions for all subsequent Api calls."""
        if self.session:
            self.session.close()
        self.session = Session()
    
    def close_session(self) -> None:
        """Close an open session, if any."""
        if self.session:
            self.session.close()
        self.session = None
    
    def response_as_json(self) -> str:
        """Return the response content as (unicode) parsable json."""
        if self.response is not None: 
            try:
                return self.response.text
            except RuntimeError as e: # from Requests, if we just downloaded a file
                return f'"RuntimeError: {e}"' #TODO maybe just return 'null' ?
        return 'null' # hopefully still valid json!
        
    def _xxx_apicall(self, url: str, method: str = 'GET', headers: dict|None = None, 
                params: dict|None = None, json: dict|None = None, 
                filename: Path|None = None, 
                upload_files: list|None = None) -> Apiresp:
        #TODO this is the old apicall, to be removed soon
        self.apicalls += 1
        call = self.session.request if self.session else request
        if headers is None:
            headers = {'Content-Type': 'application/json',
                       'Accept': 'application/json'}
        headers.update(
            {'Authorization': f'Bearer {self.configurator.config["GRIST_API_KEY"]}'})

        if filename is not None: # download mode, method *must* be GET!
            with call('GET', url, headers=headers, params=params, 
                      stream=True, **self.request_options) as resp:
                self.ok = resp.ok
                self._save_request_data(resp)
                if self.configurator.raise_option:
                    resp.raise_for_status()
                if resp.ok:
                    with open(filename, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=1024*100):
                            f.write(chunk)
            return resp.status_code, None
        elif upload_files: # upload mode, method *must* be POST!
            # TODO: "uploaded_files" must be ready for the call, 
            # i.e. opening/closing files is handled by the calling function
            # not sure if it's the best option, but for now...
            resp = call('POST', url, headers=headers, 
                        files=upload_files, **self.request_options)
            self.ok = resp.ok
            self._save_request_data(resp)
            if self.configurator.raise_option:
                resp.raise_for_status()
            return resp.status_code, resp.json() if resp.content else None
        else: # ordinary request
            resp = call(method, url, headers=headers, params=params, 
                        json=json, **self.request_options) 
            self.ok = resp.ok
            self._save_request_data(resp)
            if self.configurator.raise_option:
                resp.raise_for_status()
            return resp.status_code, resp.json() if resp.content else None

    def apicall(self, url: str, method: str = 'GET', headers: dict|None = None, 
                params: dict|None = None, json: dict|None = None, 
                filename: Path|None = None, 
                upload_files: list|None = None) -> Apiresp:
        """The engine responsible for actually calling the Apis."""
        # TODO: in upload mode, "upload_files" must be ready for the call, 
        # i.e. opening/closing files is handled by the calling function
        # not sure if it's the best option, but for now...
        self.request: PreparedRequest|None = None
        self.response: Response|None = None
        if headers is None:
            headers = {'Content-Type': 'application/json',
                       'Accept': 'application/json'}
        headers.update({'Authorization': 
                        f'Bearer {self.configurator.config["GRIST_API_KEY"]}'})
        # first, we prepare the request
        req_opts = self.request_options
        if filename: # download mode, method *must* be GET!
            method = 'GET'
            req_opts = {'stream': True, **self.request_options}
        elif upload_files: # upload mode, method *must* be POST!
            method = 'POST'
        r = Request(method, url, headers=headers, params=params, 
                    json=json, files=upload_files)
        session = self.session or Session()
        self.request = session.prepare_request(r)
        if self.dry_run: # we want to fake an ok call as far as possibile
            self.ok = True
            return 200, {'No Content': 'Pygrister is running dry!'}
        # then, we post the prepared request
        self.response = session.send(self.request, **req_opts)
        self.apicalls += 1
        self.ok = self.response.ok
        if self.configurator.raise_option:
            self.response.raise_for_status()
        if filename and self.ok:
            with open(filename, 'wb') as f:
                for chunk in self.response.iter_content(chunk_size=1024*100):
                    f.write(chunk)
            self.response.close()
            return self.response.status_code, None
        return (self.response.status_code, 
                self.response.json() if self.response.content else None)

    def inspect(self, sep: str = '\n', max_content: int = 1000) -> str:
        """Collect info on the last api call that was requested (and possibly 
        responded to) by the server. 

        Use ``sep`` to set a custom separator between elements, 
        and ``max_content`` to limit the response content size. 

        Intended for debug: add a ``print(self.inspect())`` right after the 
        call to inspect. Works even if the server returned a "bad" status 
        code. If server did not respond, only request data will be recorded. 
        """
        cfg = '->Pygrister config.: '
        cfg += f'{self.configurator.config2output(self.configurator.config)}'
        req = self.request
        res = self.response
        if req is None:
            return f'->Req.: no request data{sep}{cfg}'
        txt = f'->Req. url: {req.url}{sep}'
        txt += f'->Req. method: {req.method}{sep}'
        headers = dict(req.headers)
        prot, key = headers['Authorization'].split()
        key = apikey2output(key)
        headers['Authorization'] = f'{prot} {key}'
        txt += f'->Req. headers: {headers}{sep}'
        txt += f'->Req. body: {req.body}{sep}'
        if res is None:
            txt += f'->Resp.: no response data{sep}{cfg}'
            return txt
        txt += f'->Resp. url: {res.url}{sep}'
        txt += f'->Resp. result: {res.status_code} {res.reason}{sep}'
        txt += f'->Resp. headers: {res.headers}{sep}'
        txt += f'->Resp. content: {self.response_as_json()[:max_content]}{sep}'
        txt += cfg
        return txt
