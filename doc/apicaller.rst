.. _apicall_engine:

The API call engine.
====================

The code responsible for posting the API call to the Grist server lives in 
a separate ``pygrister.apicaller.ApiCaller`` class. The main ``GristApi`` 
class will load a default instance of ``ApiCaller`` at instantiation time. 
You may write your custom API call engine and pass it to 
``GristApi.__init__``, as the optional argument ``custom_apicaller``: 
of course, this is not needed in normal usage. 

Once the ``GristApi`` instance is ready, its internal API caller will be 
accessible via the ``GristApi.apicaller`` attribute. Accessing the 
API caller directly may help you with debugging. 

(Why should you want to write a custom Api caller? For instance, our 
Gry command line tool makes use of a custom caller to enforce a different 
pattern of error handling when calling the APIs: since Gry is meant for 
the final user, we wanted to catch any possible connection error and 
present a nice message instead of the crude stacktrace that a normal 
``GristApi`` instance would emit before crashing out. You may read the 
source code in ``gry.py`` to see a custom Api caller at work.)


.. _apicallers_configurators:

API callers and configurators.
------------------------------

An ``ApiCaller`` class will need its own configurator: you may write a 
custom class, or simply use the default one::

  >>> from pygrister.config import Configurator
  >>> from pygrister.apicaller import ApiCaller
  >>> from pygrister.api import GristApi
  >>> class MyApiCaller(ApiCaller):
  ...    pass  # insert here your custom logic for api calling
  
  >>> a = MyApiCaller()  # a custom api caller using the default configurator
  >>> grist = GristApi(custom_apicaller=a)

Then, the ``GristApi`` class will also use the configurator provided with the 
api caller::

  >>> grist.configurator is grist.apicaller.configurator
  True

To ensure that both ``GristApi`` and its api caller will use the same configurator, 
you are prevented to pass both a ``custom_configurator`` and a ``custom_apicaller``  
to the ``GristApi`` constructor::

  >>> GristApi(custom_configurator=c, custom_apicaller=a) # throws an exception

Once ``GristApi`` is instantiated, it is possible to change the configurator 
(and/or the api caller) at runtime... in theory, but this is not really supported. 
You must always remember to ensure that ``GristApi`` and its own internal api 
caller will use the same configurator object, at any time. For instance, ::

  >>> class MyConfigurator(Configurator): pass  # a custom configurator

  >>> conf = MyConfigurator()
  >>> grist.configurator = conf # change the configurator at runtime
  >>> grist.apicaller.configurator = conf # change the apicaller's one too!

This is possible, if convoluted. If you really must swap configurator 
and/or api caller at runtime, it's easier to create two separate instances 
of ``GristApi``, with their own different internals, then swap between them  
instead. 

