.. _pygrister_configuration:

Pygrister configuration.
========================

In everyday use, you will need Pygrister to push/pull data from a single 
document and very little else. Working with multiple documents, workspaces 
and sites is rarely needed. Pygrister comes with a configuration system 
to register your defaults for common operations, while still allowing you to 
switch gears at any time. 

For example, to retrieve data from a table, you would call the Grist API 
endpoint as ::

    https://<myteam>.getgrist.com/api/docs/<docID>/tables/<tableID>/records

thus providing every time also your team and document IDs (not to mention, 
the Api key to be included in the request payload). In Pygrister, you'll 
have those values already stored in the configuration, so it's just a matter 
of calling ::

    >>> grist = GristApi()
    >>> grist.list_records('Table1')

However, when you need to specify a different team/document, Pygrister 
allows you to fill in the new information as optional parameters::

    >>> grist.list_records('Table1', doc_id='mydoc', team_id='myteam')

Pygrister's configuration system may seem a little convoluted at first, 
as we try to accomodate for many possible use cases. Basically, you have 

- "static configuration" first, declared *before* instantiating the 
  ``GristApi`` class, that will be parsed and loaded into ``GristApi``: 
  most of the time, this is all you need; 
- then, "runtime configuration" that is, several ways in which you may 
  add or change configuration during the lifetime of your ``GristApi`` 
  instance. 


Where configuration is stored.
------------------------------

Pygrister "static" configuration is a set of key/value pairs stored

- first, in a ``config.py`` file located in Pygrister's installation directory, 
  along with the other Python modules. This is intended to provide sensible 
  default values for each configuration key: you should never modify this 
  file directly;
- then, in a ``~/.gristapi/config.json`` file that you can leave in your home 
  directory to override the defaults with your own preferences. You are free 
  to put there just the keys for which you want to change the default value;
- finally, you may also supply your values as environment variables.

Note that a value declared in one place will override those in the lower 
layers. For instance, if you do nothing, the value for the ``GRIST_TEAM_SITE`` 
key will default to ``docs``; if you write something like 
``"GRIST_TEAM_SITE": "myteam"`` in your json file, then it will be ``myteam``; 
then, if you also set a ``GRIST_TEAM_SITE`` env variable, that will be 
the final value. 

You don't need to provide either a ``~/.gristapi/config.json`` file or env 
variables: you can choose one or the others, or a mix of the two. Environment 
variables can be prepared in the shell before launching your Python program, 
or even added at runtime, right before instantiating the ``GristApi`` class. 
Nothing stops you from doing something like ::

    >>> os.environ['GRIST_TEAM_SITE'] = 'mysite'
    >>> grist = GristApi()

in your code. However, this is not really necessary since Pygrister provides 
3 more ways of overriding configuration at runtime.


Runtime configuration.
----------------------

At runtime, you may pass an optional ``config`` parameter to the ``GristApi`` 
constructor, to override any "static" configuration previously defined::

    >>> grist = GristApi(config={'GRIST_TEAM_SITE': 'mysite'})

In addition, at any time you may call either ``GristApi.reconfig`` or 
``GristApi.update_config`` to change the configuration (the difference 
between the two will be explained below)::

    >>> grist.update_config(config={'GRIST_TEAM_SITE': 'mysite'})

This will affect all API calls from now on. 

Finally, specific API call functions may provide optional parameters to 
temporarily override the configuration. For instance, this ::

    >>> st_code, res = grist.list_records('mytable')

will fetch records from a table in your current working document (as per config). 
However, if you need to quickly pull data from another document just once, 
this ::

    >>> st_code, res = grist.list_records('another_table', doc_id='another_doc')

will do the trick without having to change configuration. 


Working with the configuration.
-------------------------------

The top-level function ``pygrister.api.get_config`` returns the current 
"static" configuration, calculated from Pygrister's defaults, your json file 
and environment variables. 

The runtime configuration currently in use is stored in the 
``GristApi.configurator.config`` attribute. In addition, the function 
``GristApi.inspect`` will also output the configuration, among other things.

::

    >>> from pygrister.api import get_config, GristApi
    >>> grist = GristApi({'GRIST_TEAM_SITE': 'myteam'})
    >>> get_config() # static configuration
    {..., 'GRIST_TEAM_SITE': 'docs', ...}
    >>> grist.configurator.config # runtime configuration currently in use
    {..., 'GRIST_TEAM_SITE': 'my_team', ...}

Changing configuration at runtime.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

As mentioned earlier, you may call either ``GristApi.reconfig`` or 
``GristApi.update_config`` to change the configuration at runtime. 

The difference between the two is that ``reconfig`` will re-build your 
configuration from scratch (ie., from the config file and/or environment 
variables), *then* apply your modifications, if any; ``update_config`` 
will apply your changes on top of the existing (runtime) configuration, 
incrementally. ::

    >>> g = GristApi()
    >>> g.update_config({'GRIST_TEAM_SITE': 'mysite'})
    >>> g.update_config({'GRIST_SAFEMODE': 'Y'})
    >>> # incremental modifications are applied as expected
    >>> g._config['GRIST_TEAM_SITE'], g._config['GRIST_SAFEMODE']
    ('mysite', 'Y')
    >>> g.reconfig({'GRIST_SAFEMODE': 'N'})
    >>> # reconfig re-builts configuration, so here team site is "docs" again
    >>> g._config['GRIST_TEAM_SITE'], g._config['GRIST_SAFEMODE']
    ('docs', 'N')

Just call ``reconfig`` without arguments to revert to the original "static" 
configuration.


Configuration keys.
-------------------

Finally, this is a list of all the config keys currently defined and 
their default values, as defined in the ``config.py`` module::

    {
        'GRIST_API_KEY': '<your_api_key_here>',
        'GRIST_SELF_MANAGED': 'N',
        'GRIST_SELF_MANAGED_HOME': 'http://localhost:8484',
        'GRIST_SELF_MANAGED_SINGLE_ORG': 'Y',
        'GRIST_SERVER_PROTOCOL': 'https://',
        'GRIST_API_SERVER': 'getgrist.com',
        'GRIST_API_ROOT': 'api',
        'GRIST_TEAM_SITE': 'docs',
        'GRIST_WORKSPACE_ID': '0',  # this should be a string castable to int
        'GRIST_DOC_ID': '<your_doc_id_here>',
        'GRIST_RAISE_ERROR': 'Y',
        'GRIST_SAFEMODE': 'N',
    }

**Please note**: configuration values *must be non-empty strings*. If you 
don't need a config key, just leave the default value as it is: do not 
override it with an empty string!

``GRIST_API_KEY`` is your secret API key. You may want to provide it only 
as an environment variable, for added security.

``GRIST_SELF_MANAGED``, ``GRIST_SELF_MANAGED_HOME`` and 
``GRIST_SELF_MANAGED_SINGLE_ORG`` are intended for self-hosted Grist, and 
will be :ref:`detailed separately<self_hosted_support>`. 

``GRIST_TEAM_SITE`` is your team ID. The ``docs`` default points to your 
personal site (the "@my-name" one). 

``GRIST_SERVER_PROTOCOL``, ``GRIST_API_SERVER`` and ``GRIST_API_ROOT`` 
are the remaining components of the SaaS Grist Api url: you should never 
override the default values unless you know what you are doing.

``GRIST_WORKSPACE_ID`` is your workspace ID: in fact, very few APIs make use 
of this value, and you may not need it at all. In Grist, workspace IDs are 
integers, so you must provide a string castable to ``int`` (eg. ``"42"``).

``GRIST_DOC_ID`` should be set to the ID of the document you work with the most. 
If your workflow involves constant switching between various documents, you may 
be better off leaving the default value here, and provide the actual IDs at runtime. 

``GRIST_RAISE_ERROR``: if set to ``Y`` (the default), Pygrister will raise an 
exception if something went wrong with the API call. This will be discussed 
:ref:`later on<errors_statuscodes>`. 

``GRIST_SAFEMODE``: set this value to ``Y`` to put Pygrister in 
:ref:`safe mode<safe_mode>`, where no writing API calls is allowed. 
