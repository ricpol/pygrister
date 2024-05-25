Pygrister configuration.
========================

In everyday use, you will need Pygrister to push/pull data from a single 
document and very little else. Working with multiple documents, workspaces 
or even sites is rarely needed. Pygrister comes with a configuration system 
to register your defaults for common operations, while still allowing you to 
switch gears at any time. 

For example, to retrieve data from a table, you would call the Grist API 
endpoint ::

    https://<myteam>.getgrist.com/api/docs/<docID>/tables/<tableID>/records

thus providing every time also your team and document IDs. In Pygrister, you'll 
have those values already stored in the configuration, so it's just a matter 
of calling ::

    grist = GristApi()
    grist.see_records('Table1')

However, if you need to specify a different team/document, Pygrister 
allows you this too::

    grist.see_records('Table1', doc_id='...', team_id='...')


Where configuration is stored.
------------------------------

Static configuration.
^^^^^^^^^^^^^^^^^^^^^

Pygrister configuration is a set of key/value pairs stored

- first, in a ``config.py`` file situated in the installation directory, 
  along with the other Python modules. This is intended to provide sensible 
  default values for each configuration key, and you should never modify this 
  file directly;
- then, in a ``~/.gristapi/config.json`` file that you can leave in your home 
  directory to override the defaults with your own preferences. You are free 
  to put here just the values you want to modify;
- finally, you may supply your values as environment variables.

Note that a value declared in a place will override those in the lower 
layers. For instance, if you do nothing, the value for the ``GRIST_TEAM_SITE`` 
key will default to ``docs``; if you write something like 
``"GRIST_TEAM_SITE": "myteam"`` in your json file, then it will be ``myteam``; 
then, if you also set up a ``GRIST_TEAM_SITE`` env variable, this one will be 
the chosen value. 

You don't need to provide either a ``~/.gristapi/config.json`` file or env 
variables: you can choose one or the others, or a mix of the two. Environment 
variables can be prepared in the shell before launching your Python program, 
or simply added at runtime, before instantiating the ``GristApi`` class. 
Nothing stops you from doing something like ::

    os.environ['GRIST_TEAM_SITE'] = 'mysite'
    grist = GristApi()

in your code. 

Runtime configuration.
^^^^^^^^^^^^^^^^^^^^^^

However, Pygrister provides 3 more ways of overriding configuration at runtime. 

First, you may pass an optional ``config`` parameter to the ``GristApi`` 
constructor, to override any "static" configuration previously defined::

    grist = GristApi(config={'GRIST_TEAM_SITE': 'mysite'})

Second, at any time you may call ``GristApi.reconfig`` to change the 
configuration::

    grist.reconfig(config={'GRIST_TEAM_SITE': 'mysite'})

This will affect all the API calls from now on. 

Finally, specific API call functions may provide optional parameters to 
temporarily override the configuration. For instance, this ::

    st_code, res = grist.see_records('mytable')

will fetch records from a table in your current working document (as per config). 
If you need to quickly pull data from another document just once, there's no 
need to change your configuration: a simple ::

    st_code, res = grist.see_records('another_table', doc_id='......')

will do the trick. 

The function ``api.get_config`` returns the current "static" configuration, 
i.e. taking into account only the json files and environment variables. At 
runtime, you may inspect the variable ``GristApi.config`` to know the "real", 
actual configuration in use. 


Configuration keys.
-------------------

This is the content of the ``config.py`` file, listing all the config keys 
currently defined, and their default values::

    {
        "GRIST_API_KEY": "<your key here>",
        "GRIST_SERVER_PROTOCOL": "https://",
        "GRIST_TEAM_SITE": "docs",
        "GRIST_API_SERVER": "getgrist.com/api",
        "GRIST_WORKSPACE_ID": "<your ws id here>",
        "GRIST_DOC_ID": "<your doc id here>",
        "GRIST_RAISE_ERROR": "Y",
        "GRIST_SAFEMODE": "N"
    }

**Please note**: configuration values *must* be non-empty strings. If you 
don't need a config key, just leave the default value as it is: do not 
override it with an empty string!

``GRIST_API_KEY`` is your secret API key. You may want to provide it only 
as an environment variable, for added security.

``GRIST_TEAM_SITE`` is your team ID. The ``docs`` default points to your 
personal site (the "@my-name" one). 

``GRIST_SERVER_PROTOCOL`` and ``GRIST_API_SERVER`` are the remaining components 
of the Grist Api url: do not override the default values. Support for 
self-hosting and custom urls is not yet available. 

``GRIST_WORKSPACE_ID`` is your workspace ID: in fact, very few APIs make use 
of this value, and you may not need it at all. 

``GRIST_DOC_ID`` is the ID of the document you work the most. If your workflow 
involves constant switching between various documents, you may be better off 
leaving the default value here, and provide the actual IDs at runtime. 

``GRIST_RAISE_ERROR``: if set to ``Y`` (the default), Pygrister will raise an 
exception if something went wrong with the API call. This will be discussed later 
on. 

``GRIST_SAFEMODE``: if Pygrister is in safe mode (set this value to ``Y``), 
no writing API calls will be allowed. 

*Note*: extensions and subclasses may add other config keys as needed. 
Pygrister will incorporate them in the design explained here.


App-specific configuration.
---------------------------

Having multiple config json files for different applications/workflows is not 
supported. However, this is hardly a problem: just provide your custom json 
file and load it at runtime::

    with open('myconfig.json', 'r') as f:
        myconfig = json.loads(f.read())
    
    grist = GristApi(config=myconfig)

If you change things, and then you need to come back to your starting config, 
then you just have to call ::

    grist.reconfig(config=myconfig)


"Cross-site" access.
--------------------

We call it a cross-site access when you try reaching an object belonging to a 
team site "from" a different team site, i.e. calling 
``https://mysite.getgrist.com/api/...`` to reach something that does not belong 
to ``mysite``. 

The general rule, here, is that all the ``/docs`` APIs do not allow cross-site 
operations, while other endpoints are fine. For example, trying to reach a 
document ``https://<site>.getgrist.com/api/docs/<doc_id>`` will result in an 
HTTP 404 if ``<doc_id>`` does not belong to ``<site>``. On the other hand, 
something like ``https://<site>.getgrist.com/api/workspaces/<ws_id>`` will work, 
even if the workspace is not in ``<site>``. 

In terms of Pygrister's own interface, there's little we can do about this. 
Most of the time, you will work with a single team site, so you'll do the 
right thing anyway. If your workflow involves switching between sites, be 
careful that the resource you're trying to contact belongs to your "current" 
team site (as per configuration). For instance, this will not work::

    doc1 = '<doc1_ID>' # belongs to "myteam1"
    doc2 = '<doc2_ID>' # belongs to "myteam2"
    g = GristApi(config={'GRIST_TEAM_SITE': 'myteam1'})
    g.see_doc(doc1) # ok
    g.see_doc(doc2) # HTTP 404

In such cases, it is always better to pass the arguments explicitly, 
to avoid confusion::

    g.see_doc(doc1, team_id='myteam1')
    g.see_doc(doc2, team_id='myteam2')

