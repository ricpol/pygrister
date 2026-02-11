Various and sundry.
===================

.. _inspecting_api_call:

Inspecting and troubleshooting the API call.
--------------------------------------------

It goes without saying, Pygrister relies on the excellent Python Requests 
library to do the actual talking with the Grist API. Every time a request 
is sent, and a response is retrieved, Pygrister saves the relevant details 
of both for subsequent inspection. 

The underlying Requests' 
`PreparedRequest <https://requests.readthedocs.io/en/latest/api/#requests.PreparedRequest>`_ 
object (which is your API call, ready to be posted) will be accessible as 
``GristApi.apicaller.request``. Once the response is retrieved, the 
`Response <https://requests.readthedocs.io/en/latest/api/#requests.Response>`_ 
object will be available as ``GristApi.apicaller.response``. 
(If you are wondering about the ``apicaller`` bit above, read the section 
devoted to :ref:`custom Api callers<apicall_engine>`.)

The convenience function ``GristApi.inspect`` will collect and output the 
relevant data of both PreparedRequest and Response for you. 
You may call it if anything goes wrong: pass an optional ``sep`` argument to 
set a custom separator between the various elements (eg, pass ``sep=' --- '`` 
instead of the default ``\n`` to produce a one-liner dump suitable for logging). 
You may also pass a ``max_content`` argument to limit the size of both 
request's and response's body. 

The inspect data always refer to the *last* API call that was posted, either 
successfully or not. You should call ``inspect`` and/or access the Requests' 
objects *before* making the next API call. 

If the API call returned a "bad" status code (eg, Http 404, Http 500 etc.), 
the response object will still be available. If, however, the call was not even 
responded to by the server (eg, timed out), then ``GristApi.apicaller.response`` 
will be ``None``.


.. _errors_statuscodes:

Errors vs Status codes.
-----------------------

When you receive a response, but the Http status code is "bad" 
(that is, 300 or more), the underlying Requests library may optionally 
throw and exception - and Pygrister offers you the same choice. 

If you set the ``GRIST_RAISE_ERROR`` config key to ``Y`` (the default), then 
Pygrister will raise a ``requests.HTTPError`` if the response is not ok. 
Otherwise, Pygrister will simply return the bad response as if nothing.

Keep in mind that both status code and response body will always be retrieved: 
upon success, they will be returned by the API call function as usual; if 
an HTTPError occurred *and you choose to raise it*, you can still access the 
retrieved data via the ``GristApi.apicaller.response`` object.

Since the response is delivered in any case, it is really just a matter of taste. 
If you prefer "to ask for forgiveness", set the config key to ``Y`` (the default) 
and prepare for the possible exception::

    >>> from requests import HTTPError
    >>> from pygrister.api import GristApi

    >>> grist = GristApi()
    >>> try: 
    ...     st_code, res = grist.list_records('mytable')
    ... except HTTPError:
    ...     # there's no "st_code" and "res" but data have been retrieved anyway
    ...     st_code = grist.apicaller.response.status_code 
    ...     res = grist.apicaller.response.text  # or .json()

If you prefer to "look before you leap" instead, set the config key to ``N`` 
and check the resulting status code::

    >>> grist.reconfig({'GRIST_RAISE_ERROR': 'N'})
    >>> st_code, res = grist.list_records('mytable')
    >>> if st_code >= 300:
    ...     # now the function is allowed to return even if an error occurred
    ...     print(st_code, res)

Finally note that, if an HTTPError occurred, the body of the retrieved response 
will of course not conform to the "regular" Pygrister format for a successful 
request::

    >>> grist.reconfig({'GRIST_RAISE_ERROR': 'N'})
    >>> grist.list_records('bogus_table') # usually, response here is a list
    (404, {'error': 'Table not found "bogus_table"'})
    >>> grist.add_records('Table1', ['bogus_records']) # usually, resp. is None
    (400, {'error': 'Invalid payload', 'details': 
    {'userError': 'Error: body.records[0] is not a NewRecord; (...)}})

In such cases, Pygrister will always return the original Grist API response 
without modification. 


The ``ok`` attribute.
---------------------

As a shortcut, the ``GristApi.ok`` attribute is set to ``True`` if the last 
request was both received and successful (status code < 300), to ``False`` 
otherwise. This is useful especially if you choose not to raise errors: 
instead of inspecting the status code, you may then write something like ::

    >>> grist.reconfig({'GRIST_RAISE_ERROR': 'N'})
    >>> st_code, res = grist.list_records('mytable')
    >>> if grist.ok:  # equivalent to "if st_code < 300"
    ...     do_something()

Note, however, that this pattern only works if the response was retrieved in 
the first place. If the server eg. timed out, Requests (and Pygrister) will 
throw the appropriate exception (``requests.Timeout`` for example) well before 
you have a status code and a response body to manipulate. If you catch the 
exception and keep the ``GristApi`` instance alive, however, you will find 
that ``GristApi.ok`` has been set to ``False`` by default: this doesn't mean 
a "bad" status code occurred (because, in fact, there is no status code), 
but it can be helpful in log parsing and post-mortem inspection. 

To sum up, ``GristApi.ok`` 

- is ``False`` when a response was not retrieved at all (but you have 
  to catch the subsequent Requests exception first);
- is ``False`` when a response was received, with a "bad" status code 
  (*if* you set your ``GRIST_RAISE_ERROR`` config key to ``Y``, then you  
  still have to catch a ``requests.HTTPError`` though);
- is ``False`` when Pygrister is in "dry run mode", see below;
- is ``True`` when a response was received and the status code is "good". 


Dry run.
--------

Set ``GristApi.apicaller.dry_run = True`` to enter "dry run mode", where 
you go as far as to prepare the request, but you never actually post it. 
Set it back to ``False`` to return to normal functioning.

While in dry run mode: 

- a ``GristApi.apicaller.request`` object will always be prepared;
- ``GristApi.apicaller.response`` will always be ``None`` because 
  the request will not be posted;
- ``GristApi.ok`` will be ``False``;
- any api call will return a fake response, with Http 418 status code and  
  a warning message as the response body;
- even if the fake response has a "bad" status code, ``requests.HTTPError`` 
  will never be raised (even if your ``GRIST_RAISE_ERROR`` config key says 
  otherwise).

The latter 3 conditions may sound a little odd, but we wanted dry run mode 
to fake a response anyway, instead of throwing an exception. 
And yes, the returned status code is the infamous and unused 
`418 I'm a teapot <https://en.wikipedia.org/wiki/Hyper_Text_Coffee_Pot_Control_Protocol>`_, 
so that you will know that this is not serious business after all ::

    >>> grist = GristApi()
    >>> grist.apicaller.dry_run = True
    >>> grist.see_team()
    (418, {'No Content': 'Pygrister teapot is running dry!'})


.. _safe_mode:

Safe mode.
----------

If you set the ``GRIST_SAFEMODE`` configuration key to ``Y``, all API call 
functions attempting a write operation will be blocked: Pygrister will throw 
a ``GristApiInSafeMode`` exception instead. 

This is meant as a higher-level block than the "dry run" mentioned above. 
However, safe mode actually works by temporary switching to dry run mode, 
so that, if you catch the exception, you can still inspect the prepared 
request afterwards::

    >>> from pygrister.exceptions import GristApiInSafeMode
    >>> grist = GristApi({'GRIST_SAFEMODE': 'Y'})
    >>> try: 
    ...     grist.add_workspace('bogus')
    ... except GristApiInSafeMode:
    ...     pass
    ...
    >>> grist.apicaller.request
    <PreparedRequest [POST]>

Please note that the two ``run_sql*`` functions are still allowed in safe mode, 
because the underlying API only accepts ``SELECT`` statements anyway. 


.. _additional_args_request:

Additional arguments for the request.
-------------------------------------

You may pass optional arguments, not otherwise used by Pygrister, to the underlying 
`Requests call <https://requests.readthedocs.io/en/latest/api/#requests.request>`_. 
Simply set ``GristApi.apicaller.request_options`` to a dictionary::

    >>> grist = GristApi()
    >>> grist.apicaller.request_options = {'timeout': 5}

The ``request_options`` will then be injected into all subsequent Pygrister API 
calls. The code above, for example, will set a timeout limit from now on. 


Using Requests sessions in Pygrister.
-------------------------------------

Requests supports using 
`sessions <https://requests.readthedocs.io/en/latest/user/advanced/#session-objects>`_ 
to persist connection data, and so does Pygrister. 

Working with sessions is straightforward::

    >>> grist = GristApi({...})
    >>> grist.open_session()  # open a new session
    >>> grist.session         # this is how you know you are in a session
    <requests.sessions.Session object at ...>
    >>> # ...Pygrister api calls are now "inside" the session...
    >>> grist.close_session() # close the session
    >>> grist.session         # "session" attribute is now None
    >>>

As long as you are in a session, all subsequent api calls will re-use the same 
underlying connection, resulting in much faster interaction. From the 
second api call on, if you inspect the request headers (``grist.req_headers``), 
you will notice a new ``'Cookie'`` element added by Requests to persist the 
connection. 

In Pygrister, session have no other use than for boosting performance, and they 
are transparent to the rest of the api. Inside a session, you will use the 
``GristApi`` class just the same: start a session, and then forget about it. 

You may use sessions for performance, when you need to post several api calls 
in a row (like, in a script). However, keep in mind that Requests 
(and Pygrister) sessions are supplied "as it is" - your server may be 
configured to expire a session after a while, for instance. 
