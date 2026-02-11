Advanced Gry topics.
====================

The following, more advanced features of Gry will require an understanding 
of how Pygrister works, and/or some Python skills. 


Data type converters.
---------------------

:ref:`Pygrister converters<converter_functions>` can be very helpful 
in ``gry``, especially in writing operations, because it's difficult 
to express anything other than strings in the command line.

If you want to include converters in your ``gry`` workflow, you must add 
a Python module named ``cliconverters.py`` *in your current directory* 
(in fact, you can put the file anywhere in your Python path, since ``gry`` 
will attempt to *import* it). 

**Standalone version**: In the standalone bundle, you may also drop your 
``cliconverters.py`` in the top-level directory of the bundle, ie next to the 
"gry.exe" and readme files. You will find a stub module there, for you 
to open and edit.

Inside the file, write your converter functions as you need. 
You must, however, name the final converter dictionaries ``cli_out_converters`` 
and ``cli_in_converters``. These converters will be imported and applied 
to your ``gry`` call.


Passing additional arguments to Requests.
-----------------------------------------

:ref:`In Pygrister<additional_args_request>`, you may set 
``GristApi.apicaller.request_options`` to a dictionary in order to pass 
optional arguments, not otherwise used by Pygrister, to the underlying 
Requests call. You can't do this in Gry, as you don't have direct access 
to the ``GristApi`` class. 

If you need to pass arguments to Requests, just drop a ``gryrequest.json`` 
file *in your current directory*. This file will be parsed at runtime, 
and its content will be feeded to ``GristApi.apicaller.request_options`` 
as it is. For instance, ::

  {
      "timeout": 15,
      "verify": false,
      "allow_redirects": true
  }

See the Requests documentation for the available options. 

**Standalone version**: In the standalone bundle, ``gryrequest.json`` must 
be located in the top-level folder of the bundle. You will find a stub there, 
for you to open and edit.

Please note that the Gry-specific ``GRIST_GRY_TIMEOUT`` configuration 
may also be used to set a timeout for the Requests call. This is meant 
as a shortcut, since a timeout is almost always wanted. If a timeout is 
all you need, just set the config key. For anything more than this, 
you'll need a separate ``gryrequest.json`` file. If a timeout setting 
is found in both places, ``gryrequest.json`` will take precedence 
(if in neither place, Gry will default to 60 seconds anyway).

The ``gry conf`` command will output both the current Gry settings, and 
any Requests additional arguments you may have set. 


The ``gry`` Python shell.
-------------------------

Entering the ``gry python`` command gives you access to a patched Python shell, 
complete with a pre-loaded Pygrister environment. Inside, the ``gry`` variable 
is an instance of ``pygrister.GristApi``: its configuration is the same of the 
``gry`` cli tool, at the moment of starting the Python shell::

  % gry python
  This is Python <...> on <...>, and Pygrister <...>
  Here, "gry" is a ready-to-use, pre-configured GristApi instance.
  >>> gry
  <GristApi instance at 0x....>
  >>> gry.configurator.config
  {... <the same config of the gry tool> ...}
  >>> gry.see_doc()  # etc. etc.
  ...
  >>> exit()

This is meant as a quick way to switch to a more powerful tool when you need 
to express an API call too sophisticated for ``gry`` to handle. 

Type ``exit()`` to return to your system command line.

If you add the ``--idle`` option, an Idle window will open instead, provided that 
you have Idle installed on your system.

(More specifically: all Gry will do, is to invoke ``python`` or ``python -m idlelib`` 
from your system shell. If it doesn't work for you, perhaps because you don't have 
Python in your path or whatever, the ``gry`` command will fail too.)

Be aware that you *can* change your configuration in the Gry Python shell 
between api calls, as ``gry``, here, is just a regular ``GristApi`` instance:  
nothing stops you from invoking ``gry.reconfig({...})`` or 
``gry.update_config({...})``. However, you will return to the previous, 
"regular" Gry configuration as soon as you leave the Gry Python shell. 


Caveat and limitations.
-----------------------

There is a limit to what can be expressed from the command line, without 
over-complicating the syntax. For this reason, Gry does not map a few APIs, 
and does not include a few options. 

- Several APIs allow for writing many instances of a "thing" in a single call: 
  in Gry, it's always one thing at a time. For instance, you can add multiple 
  tables to a document with ``GristApi.add_tables``, and multiple columns to 
  a table with ``GristApi.add_cols``: the Gry equivalents ``gry table new`` 
  and ``gry col new`` are limited to one object at a time. 

- Filters in search APIs are difficult to write in the command line: Gry 
  does not provide filter options for user, attachment and record listing 
  (for the latter, an sql query is recommended instead). Unfortunately, 
  ``GristApi.search_users`` is also basically a filter, therefore Gry is not 
  implementing it at the moment. 

- Nested structures such as record, columns, etc. are difficult to express 
  as well: Gry will offer only a simplified version for adding/updating 
  records and columns. 

- The two ``GristApi.add_update_*`` APIs (for columns and records) are just too 
  complicated for Gry, as it is ``GristApi.bulk_user``. 

Some of these may be implemented in the future. In any case, remember: 
if you hit a construct that you cannot express in Gry, just type 
``gry python`` to open a Python shell, pre-loaded with a working GristApi 
instance, and let Pygrister take over from there. 

Finally, keep in mind that ``gry``, being written in Python, is *slow*: 
every time you enter a ``gry`` command, the Python interpreter must be loaded 
(and then some) before your command is parsed and executed. 
In normal, interactive usage you won't even notice (because the real bottleneck 
will be the network latency anyway). However, think twice before, say, 
queuing many ``gry`` commands in a script. If you want to load 100 records 
into a table, something like this ::

    >>> records = [[...], [...], ...]
    >>> grist = GristApi()
    >>> for record in records:
    ...     _ = grist.add_record(...)

can be fast, while the equivalent ::

    #!/bin/bash
    gry rec new ... -q
    gry rec new ... -q
    ...

will be *very* slow.
