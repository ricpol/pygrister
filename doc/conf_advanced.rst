Advanced configuration topics.
==============================

.. _self_hosted_support:

Support for the self-hosted Grist.
----------------------------------

The Grist API works the same way for both the regular SaaS Grist (the 
one you get at www.getgrist.com) and the self-managed version - and so 
does Pygrister. 

To learn about the self-hosted version of Grist read the 
`Grist documentation <https://support.getgrist.com/self-managed>`_.

If you want to use Pygrister against a self-hosted Grist instance, 
you need to set up a few more configuration options. 

First, set ``GRIST_SELF_MANAGED`` to ``Y``. Then, you need to set 
``GRIST_SELF_MANAGED_HOME`` to the "home page" url of your Grist server, eg. 
``https://grist.mysite.com``. The suggested default ``http://localhost:8484`` 
is the usual access point of a test instance running locally. 

Please note: if you are serving Grist from a public host, then Pygrister's 
``GRIST_SELF_MANAGED_HOME`` must be set to the same url of the ``APP_HOME_URL`` 
variable that you will provide to the Grist environment. 

Finally, if you are running the single-team flavour of Grist, you need to 
set ``GRIST_SELF_MANAGED_SINGLE_ORG`` to ``Y`` (the default). The name of 
the team must then be specified in ``GRIST_TEAM_SITE`` (which you should never 
change at runtime, of course).

Again, remember that you will still need to provide a ``GRIST_SINGLE_ORG`` 
variable to the Grist environment, set to the same team name as in Pygrister's 
``GRIST_TEAM_SITE``.

(A little duplication here is inevitable, since Pygrister and Grist 
will usually run in completely separate environments, and they can't access 
each other's variables.)

When ``GRIST_SELF_MANAGED`` is set ``Y`` and the self-hosted Grist support is 
enabled in Pygrister, the configuration keys ``GRIST_SERVER_PROTOCOL`` and 
``GRIST_API_SERVER`` will be ignored, and ``GRIST_SELF_MANAGED_HOME`` 
will be used instead. The remaining configuration keys will work as usual. 


Support for Grist Desktop.
--------------------------

`Grist Desktop <https://github.com/gristlabs/grist-desktop>`_ is basically a 
self-hosted Grist, packaged as an Electron application: hence, Pygrister will 
work just fine there too. The only catch is that you should provide a 
``GRIST_DESKTOP_AUTH`` env variable to enable API calls, which are disabled by 
default (for instance you may set it to ``=none``, see 
`this forum thread <https://community.getgrist.com/t/using-the-api-with-grist-desktop/9271/1>`_ 
for more details). 

Also, keep in mind that Grist Deskop will use port 47478 by default. 
All things considered, a Pygrister configuration like this should work for 
Grist Desktop::

    {
        'GRIST_API_KEY': '<your_api_key_here>',
        'GRIST_SELF_MANAGED': 'Y',
        'GRIST_SELF_MANAGED_HOME': 'http://localhost:47478',
        'GRIST_SELF_MANAGED_SINGLE_ORG': 'N',
        'GRIST_TEAM_SITE': 'docs',
    }

Just set ``GRIST_DESKTOP_AUTH``, start Grist Deskop, generate an API key 
there, and you should be able to place API calls with Pygrister as well. 


App-specific configuration.
---------------------------

Having multiple config json files for different applications/workflows is not 
supported. However, this is hardly a problem: just provide your custom json 
file and load it at runtime::

    with open('myconfig.json', 'r') as f:
        myconfig = json.loads(f.read())
    
    grist = GristApi(config=myconfig)

If you change things, and then you need to revert to your starting config, 
then you just have to call ::

    grist.reconfig(config=myconfig)


"Cross-site" access.
--------------------

We call it a cross-site access when you try reaching an object belonging to a 
team site "from" a different team site, that is, calling 
``https://mysite.getgrist.com/api/...`` to reach something that does not belong 
to ``mysite``. 

The general rule, here, is that all the ``/docs`` APIs do not allow cross-site 
operations, while other endpoints are fine with it. For example, trying to reach 
a call to ``https://<site>.getgrist.com/api/docs/<doc_id>`` will result in an 
HTTP 404 if ``<doc_id>`` does not belong to ``<site>``. On the other hand, 
something like ``https://<site>.getgrist.com/api/workspaces/<ws_id>`` will work, 
even if the workspace is not in ``<site>``. 

In terms of Pygrister's own interface, there's little we can do about this. 
Most of the time, you will work with a single team site, so you'll do the 
right thing anyway. If your workflow involves switching between sites, be 
aware that the resource you're trying to contact must belong to your "current" 
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


Extending the configuration.
----------------------------

If you are extending Pygrister in your custom application, know that you 
may also add other config keys as needed, besides the standard set provided 
by Pygrister. 

Pygrister will simply incorporate any additional configuration key that 
you may provide in the configuration mechanism explained earlier. Your 
``GristApi`` instance (of custom subclass) may then use the added 
configuration as you please.

For instance, our test suite runs a standard ``GristApi`` instance, but also 
adds several custom keys to the configuration file, to include or skip some 
test, depending on the environment. 


Custom configurators.
---------------------

A "configurator" class deals with the Pygrister configuration behind the scenes. 
The default configurator is ``pygrister.config.Configurator``, and the 
``GristApi`` class will load it when instantiated. 

You may want to write your own, different configurator, deriving from 
``config.Configurator``. Then, you can pass it to the ``GristApi`` 
constructor as the ``custom_configurator`` argument::

    class MyConfigurator(Configurator):
        pass # do your own thing here
    
    my_configurator = MyConfigurator(config={...})
    grist = GristApi(custom_configurator=my_configurator)

You may pass both the ``config`` and ``custom_configurator`` 
arguments to the ``GristApi`` class constructor: the custom configurator 
will be instantiated first, then ``config`` will be applied on top of it. 

The internal configurator object is exposed as the ``GristApi.configurator`` 
attribute of your ``GristApi`` instance. Swapping configurator at runtime 
is possible... but not straighforward: in fact, you will have to consider 
the "Api caller" object too. We are going to clarify this point further 
when we discuss :ref:`custom api callers<apicallers_configurators>`. 

Now that you know about ``config.Configurator``, you should also know that 
``GristApi.reconfig`` is just an alias for ``GristApi.configurator.reconfig``, 
and ``GristApi.update_config`` is really ``GristApi.configurator.update_config``. 

(All that being said - why would you want to write a custom configurator, after 
all? For instance, you may want a different way of storing the "static" 
configurations keys: just ovveride ``Configurator.get_config`` and provide 
your own logic. Our :ref:`Gry command line tool<gry_command_line>` 
makes use of a custom configurator to support different locations 
for the json configuration file: read the source code in ``cli.py`` 
for an example of a custom configurator at work.)
