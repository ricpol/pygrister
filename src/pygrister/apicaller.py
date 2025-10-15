import json as modjson
from pathlib import Path
from typing import Any
from requests import (Request, PreparedRequest, Response, 
                      Session, JSONDecodeError)

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
        self.dry_run: bool = False    #: prepare, do not post request
        self.request: PreparedRequest|None = None #: last request posted
        self.response: Response|None = None       #: last response retrieved
    
    @property
    def ok(self) -> bool:
        """``False`` if a HTTP error occurred in the response.
        
        Also, if no response was retrieved, will be ``False`` by default.
        """
        try:
            return self.response.ok # type: ignore
        except AttributeError:
            # this is debatable - Requests' "ok" only means "HTTPError"; 
            # we are extending its semantics also to every RequestException
            # where the response was not even retrieved
            return False

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
                # "or 'null'" because at least one Grist api returns '' instead
                resp = self.response.text or 'null' 
            except RuntimeError as e: # from Requests, if we just downloaded a file
                return modjson.dumps(f'RuntimeError: {e}') #TODO just return 'null'?
            # unfortunately Grist may return a non-json string!
            # eg., the case of Http 401 "invalid API key" - maybe others too
            try:
                _ = modjson.loads(resp)
            except modjson.JSONDecodeError:
                resp = modjson.dumps(resp)
            return resp
        return 'null' # hopefully still valid json!

    def apicall(self, url: str, method: str = 'GET', headers: dict|None = None, 
                params: dict|None = None, json: dict|None = None, 
                filename: Path|None = None, 
                upload_files: list|None = None) -> Apiresp:
        """The engine responsible for actually calling the Apis. 
        
        Return a ``Apiresp``-type tuple (status_code, resp_content) 
        where "resp_content" is a Json-decoded Python object 
        (usually a ``dict``, but that depends on the the specific Grist Api 
        return value and status code). 

        May throw any ``requests.RequestException`` that is not HTTP- or 
        Json- related, if a server problem occurred.
        Will throw ``requests.HTTPError`` if the status code is >=300 
        *and* the config key ``GRIST_RAISE_ERROR`` is set (default).
        Should never throw ``requests.JsonDecodeError``. 

        The ``ok`` property will be ``False`` if errors occurred. 
        """
        # TODO: in upload mode, "upload_files" must be ready for the call, 
        # i.e. opening/closing files is handled by the calling function
        # this is ugly but I can't see an obvious way to move that code here
        self.request: PreparedRequest|None = None
        self.response: Response|None = None
        if headers is None:
            headers = {'Content-Type': 'application/json',
                       'Accept': 'application/json'}
        headers.update({'Authorization': 
                        f'Bearer {self.configurator.config["GRIST_API_KEY"]}'})
        # first, we prepare the request
        req_opts = self.request_options

        # ignore ssl verification
        verify = False if self.configurator.config.get("GRIST_SSL_VERIFY", 'Y') == 'N' else True
        req_opts["verify"] = verify
        
        if filename: # download mode, method *must* be GET!
            method = 'GET'
            req_opts = {'stream': True, **self.request_options}
        elif upload_files: # upload mode, method *must* be POST!
            method = 'POST'
        r = Request(method, url, headers=headers, params=params, 
                    json=json, files=upload_files)
        session = self.session or Session()
        self.request = session.prepare_request(r)
        if self.dry_run: # let's assume a dry run equals to HTTPError...
            return 418, {'No Content': 'Pygrister teapot is running dry!'}
        # then, we post the prepared request
        self.response = session.send(self.request, **req_opts)
        self.apicalls += 1
        if self.configurator.raise_option:
            self.response.raise_for_status()
        if filename and self.ok:
            with open(filename, 'wb') as f:
                for chunk in self.response.iter_content(chunk_size=1024*100):
                    f.write(chunk)
            self.response.close()
            return self.response.status_code, None
        try:
            return self.response.status_code, self.response.json() 
        except JSONDecodeError:
            return self.response.status_code, self.response.text
        
    def inspect(self, sep: str = '\n', max_content: int = 1000) -> str:
        """Collect info on the last api call that was requested (and possibly 
        responded to) by the server. 

        Use ``sep`` to set a custom separator between elements, 
        and ``max_content`` to limit request/response body's content size. 

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
        txt += f'->Req. body: {str(req.body)[:max_content]}{sep}'
        if res is None:
            txt += f'->Resp.: no response data{sep}{cfg}'
            return txt
        txt += f'->Resp. url: {res.url}{sep}'
        txt += f'->Resp. result: {res.status_code} {res.reason}{sep}'
        txt += f'->Resp. headers: {res.headers}{sep}'
        txt += f'->Resp. content: {self.response_as_json()[:max_content]}{sep}'
        txt += cfg
        return txt
