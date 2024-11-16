Various and sundry.
===================


Safe mode.
----------

If you set the ``GRIST_SAFEMODE`` configuration key to ``Y``, all API call 
functions attempting a write operation will be blocked: Pygrister will throw 
a ``GristApiInSafeMode`` exception instead. 

Please note that the two ``run_sql*`` functions are allowed in safe mode, 
because the underlying API only accepts ``SELECT`` statements anyway. 


Troubleshooting the API call.
-----------------------------

It goes without saying, Pygrister relies on the excellent Python Requests 
library to do the actual talking with the Grist API. Every time a request 
is sent and a response is retrieved, Pygrister saves the relevant details 
of both the request and the response for subsequent inspection. 

You may check the ``req_url``, ``req_body``, ``req_headers``, ``req_method``, 
``resp_content``, ``resp_code``, ``resp_reason``, ``resp_headers``, attributes 
right after each API call to make sure Pygrister has handled the request 
correctly. 

The convenience function ``inspect`` will output all the saved data at once. 
You may call it if anything goes wrong: in fact, request/response data are 
collected even if an Http error occurred (see below). 

Please note only the first 5000 characters of a text/json response will be 
stored: this should be plenty for inspection purposes, but if you really 
need to save more, you may raise the value of the ``MAXSAVEDRESP`` constant.

Finally, binary response bodies (eg, when you download a file) will not be 
saved by default, but if you really need those too, you may set the 
``SAVEBINARYRESP`` flag. The binary string will then be stored, up to the 
``MAXSAVEDRESP`` value. 


Errors vs Status codes.
-----------------------

When you call an API and the Http status code of the response is "bad" 
(that is, 300 or more), the underlying Requests library may optionally 
throw and exception - and Pygrister offers you the same choice. 

If you set the ``GRIST_RAISE_ERROR`` config key to ``Y`` (the default), then 
Pygrister will raise a ``requests.HTTPError`` if the response is not ok. 
Otherwise, Pygrister will simply return the bad response as if nothing.

Keep in mind that both status code and response body will always be retrieved: 
upon success, they will be returned by the API call function as usual; if 
an HTTPError occurred *and you choose to raise it*, you can still access the 
retrieved data via the ``resp_code`` and ``resp_content`` attributes afterwards.

Since the response is delivered in any case, it is really just a matter of taste. 
If you prefer "to ask for forgiveness", set the config key to ``Y`` (the default) 
and prepare for the possible exception::

    from requests import HTTPError

    grist = GristApi()
    try: 
        st_code, res = grist.list_records('mytable')
    except HTTPError:
        # return values are missing but data have been retrieved anyway
        print(grist.resp_code, grist.resp_content)

If you prefer to "look before you leap" instead, set the config key to ``N`` 
and check the resulting status code::

    grist.reconfig({'GRIST_RAISE_ERROR': 'N'})
    st_code, res = grist.list_records('mytable')
    if st_code >= 300:
        # now the function is allowed to return even if an error occurred
        print(st_code, res)

Finally note that, if an HTTPError occurred, the retrieved response will 
of course not conform to the "regular" Pygrister format for a successful 
request::

    >>> grist.reconfig({'GRIST_RAISE_ERROR': 'N'})
    >>> grist.list_records('bogus_table')
    (404, {'error': 'Table not found "bogus_table"'})
    >>> grist.add_records('Table1', ['bogus_records'])
    (400, {'error': 'Invalid payload', 'details': 
    {'userError': 'Error: body.records[0] is not a NewRecord; (...)}})

In such cases, Pygrister will always return the original Grist API response 
without modification. 

The ``ok`` attribute.
^^^^^^^^^^^^^^^^^^^^^

As a shortcut, the ``GristApi.ok`` attribute is set to ``True`` if the last 
request was successful (status code < 300), to ``False`` if not. 
This is useful especially if you choose not to raise errors: instead of 
inspecting the status code, you may then write something like ::

    grist.reconfig({'GRIST_RAISE_ERROR': 'N'})
    st_code, res = grist.list_records('mytable')
    if grist.ok:  # equivalent to "if st_code < 300"
        ...


Additional parameters for the request.
--------------------------------------

You may pass optional parameters, not otherwise used by Pygrister, to the underlying 
`Requests call <https://requests.readthedocs.io/en/latest/api/#requests.request>`_. 
Simply pass a ``request_options`` parameter to the ``GristApi`` constructor, ::

    grist = GristApi(request_options={'timeout': 5})

or modify the property at runtime::

    grist.request_options = {'timeout': 5}

The ``request_options`` will then be injected into all subsequent Pygrister api 
calls. The code above, for example, will set a timeout limit from now on. 
