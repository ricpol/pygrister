from pathlib import Path
from typing import Any
#TODO remove unused imports from Requests
from requests import (request, Request, PreparedRequest, 
                      Response, Session, JSONDecodeError)

from pygrister.config import Configurator, apikey2output

MAXSAVEDRESP = 5000 #: max length of resp. content, saved for inspection
SAVEBINARYRESP = False #: if binary resp. content should be saved for inspection

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
        self.apicalls: int = 0     #: total number of API calls
        self.ok: bool = True       #: if an HTTPError occurred
        self.dry_run: bool = False #: prepare, do not post request
        self.request: PreparedRequest|None = None #: last request posted
        self.response: Response|None = None #: last response retrieved

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
            return 200, {'Error: No Content': 'Pygrister is running dry!'}
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

    def _save_request_data(self, response): #TODO not used anymore, to be removed
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

    def inspect(self) -> str: #TODO rewrite this
        """Collect info on the last api call that was responded to by the server. 
        
        Intended for debug: add a ``print(self.inspect())`` right after the 
        call to inspect. Works even if the server returned a "bad" status 
        code (aka HTTPError). Does not work if the call itself was not 
        successful (eg., timed out). 
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
        cf = self.configurator
        txt += f'->Config: {cf.config2output(cf.config)}'
        return txt
