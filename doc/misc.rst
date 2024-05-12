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
for subsequent inspection. 

If something goes wrong, you may call the ``inspect`` function to read 
the saved data of last API call you made. This works even if an Http error 
occurred (see below). 

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

Since the status code and the response body are delivered in any case, it is 
really just a matter of taste. If you prefer "to ask for forgiveness", set the 
config key to ``Y`` and prepare for the possible exception::

    from requests import HTTPError

    grist = GristApi()
    try: 
        st_code, res = grist.see_records('mytable')
    except HTTPError:
        print(grist.inspect())

If you prefer to "look before you leap" instead, set the config key to ``N`` 
and check the resulting status code::

    st_code, res = grist.see_records('mytable')
    if st_code >= 300:
        print(grist.inspect())
