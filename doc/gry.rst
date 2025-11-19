The Gry command line tool.
==========================

``gry`` is the GRist pYthon cli tool (an acronym that 
`almost makes sense <https://xkcd.com/1460/>`_). It leverages the Pygrister 
library, mapping almost all the documented Grist APIs, and providing a clean, 
easy-to-remember interface in your system shell, with no need to load/learn 
Python.

**Main features:**

- maps almost all the Grist API, with only a few inevitable simplifications;
- accepts the same configuration files/variables as Pygrister: if you can 
  post an api call with the ``GristApi`` class, then the Gry cli will work as 
  well, out of the box;
- 3 levels of output: you can choose between a nicely formatted summary for 
  human consumption, or the original Pygrister response, or even the underlying 
  Grist API retrieved response;
- easy to inspect: if a call goes wrong, just re-post it with the ``-i`` option to 
  take a peek under the hood; 
- when you need a power boost, ``gry python`` opens a Python interpreter for you, 
  with Pygrister already configured and ready to use;
- online help everywhere: just add the ``--help`` option to sort it out.

Basic usage goes as follows (where ``%`` is your shell prompt)::

    % gry team see  # get info on the "default" team as per config
    % gry doc see  # the "default" document as per config
    % gry doc see -d f4Y8Tov7TRkTQfUuj7TVdh  # select a specific document
    
    # the best way to switch to another document, from now on: 
    % export GRIST_DOC_ID=f4Y8Tov7TRkTQfUuj7TVdh  # or "set" in windows
    % gry doc see  # the same as above, but no need to add the "-d" option
    % gry doc see -d bogus_doc  # now this will fail...
    % gry doc see -d bogus_doc -i  # ...so let's see the request details 
    
    % gry ws see -w 42  # workspace info, in a nicely formatted table
    % gry ws see -w 42 -vv  # the same, in the original raw json
    
    % gry table new --help  # how do I add a table?
    % gry table new name:Text:Name age:Int:Age --table People  # like this!
    
    % gry col list -b People  # the columns of our new table
    % gry rec new name:"John Doe" age:42 -b People  # populate the table
    
    % gry sql "select * from People where age>?" -p 35  # run an sql query
    % gry python  # let's open a Python shell now!
    >>> gry.list_cols(table_id='People')  # "gry" is now a python object
    >>> exit()  # and we are back to the shell

Architecture and help online.
-----------------------------

Gry is organized in several "commands", which are *nouns* and refer to the various 
sections of the Grist API: we have ``gry doc``, ``gry table``, ``gry team`` and so on.
Each command has several "sub-commands", which describe an action to perform (and are 
mostly *verbs*). Sub-commands tend to repeat across commands: ``gry doc new`` adds 
a document, ``gry table new`` adds a table, ``gry col new`` adds a column, and so on.

Type ::

    % gry --help

to get a list of available commands. Then type, for instance, ::

    % gry doc --help

to list the sub-commands available for ``gry doc``. Finally, something like ::

    % gry doc new --help

will show you how to use a particular sub-command.

The only commands without sub-commands are 

- ``gry test`` performs a few sanity checks on your Grist setup, 
- ``gry conf`` prints your current Gry configuration,
- ``gry python`` opens a Grist-aware Python shell, 
- ``gry sql`` allows you to enter an Sql query directly, 
- ``gry version`` outputs Pygrister/Gry version.

Interactive prompt.
^^^^^^^^^^^^^^^^^^^

Traditionally, in a cli program *arguments* are required, *options* like 
``--foo, -f`` should be... well, optional (ie., with a default value). 
However, sometimes it makes sense having *required options* too - that is, 
asking for some *required* input using the more flexible *option* syntax. 
Although we try to keep this to a minimum, sometimes we can't avoid it. 
Consult the ``--help`` section of a command to find out if some options are, 
in fact, required. 

Every time an option is required, Gry also offer an *interactive prompt* for 
it: meaning, if you forget to fill in the option, Gry will offer you a second 
chance instead of just crashing out::

   % gry table new name:Text:Name age:Int:Age # ops!, must specify --table
   Insert the table ID name:

This is the *only* use we make of interactive prompts, since Gry is not designed 
to be an interactive cli tool.

Please be extra careful with this feature: while it is meant as a help in the 
interactive shell, it could just hang indefinitely a *script*!

Exit codes.
-----------

The ``gry`` tool conforms to the time-honoured Unix tradition of reporting the 
outcome with different exit codes:

- exit code ``0`` means that everything went well and the command was executed 
  without errors;
- exit code ``1`` means that an error was triggered and the command failed to 
  execute: **this is almost always a bug, and should be reported (thanks!)**;
- exit code ``2`` means that the execution was aborted because you did not enter 
  the command correctly (forgot an argument, etc.);
- exit code ``3`` means that the command was executed, but the Grist server 
  returned a "bad" Http code (like 404, 500 and so on). This is almost never 
  Gry/Pygrister's fault, but likely a problem with your configuration: retry 
  the same command with the ``-i`` option to find out more. 

Of course, exit codes are seldom needed in normal interactive use, since the 
shell will let you know anyway; they could be more useful in batch scripts. 
To inspect the exit code, type ``echo $?`` or ``echo %errorlevel%`` depending 
on your shell.

Configuration.
--------------

(Please read the doc page about Pygrister configuration, before you go on.)

If you already have a working Pygrister "static" configuration (config json file 
and/or environment variables), then the ``gry`` commands will pick it up and 
nothing more is needed. In other words, if you can start a Python shell and just 
type in ``grist = GristApi(); grist.see_team()``, then ``gry`` will work too.

On top of this, ``gry`` will also look for a ``gryconf.json`` config file located 
*in the current directory*: this is meant as a quick drop-in configuration setup, 
if you are using ``gry`` for some specific task and you don't want to change your 
Pygrister configuration, or maybe you are only interested in ``gry``, and you 
don't care about Pygrister. 

The ``gryconf.json`` config file is specific to ``gry``, and Pygrister will 
ignore it. To sum up,

- when you instantiate the ``GristApi`` class (``grist=GristApi()``), Pygrister 
  will search the configuration

      - in ``~/.gristapi/config.json`` if present
      - then in the relevant environment variables;

- when you run the ``gry`` command in your system shell instead, Pygrister will 
  look at

      - the ``~/.gristapi/config.json`` file if present, then 
      - the ``./gryconf.json`` file if present, 
      - then the relevant environment variables.

As usual, the topmost options overwrite the lower ones: environment variable, if 
given, will always take precedence.

Try ``% gry conf`` to print your current Gry configuration.

Runtime configuration.
^^^^^^^^^^^^^^^^^^^^^^

On top of the "static" configuration declared in json files and variables, all 
commands in ``gry`` accept common options to specify documents, teams, workspaces::

    % export GRIST_DOC_ID=aaaaa   # windows: set GRIST_DOC_ID=aaaaa
    % gry doc see                 # retrieve data about doc "aaaaa"
    % gry doc see -d bbbbb        # fetch doc "bbbbb" instead

is the equivalent of Pygrister's ::

    >>> grist = GristApi({'GRIST_DOC_ID': 'aaaaa'})
    >>> grist.see_doc()
    >>> grist.see_doc(doc_id='bbbbb')

Below is a list of all common options available.

In everyday use, however, you probably won't like typing in the document/team ID 
all the times: just set up the configuration file, and/or an env variable in your 
shell.

Differences with regular Pygrister configuration.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Gry will accept an additional ``GRIST_GRY_TIMEOUT`` configuration key to set 
a timeout limit for the api call. This key is *optional*: if you don't provide 
a value, default will be 60 seconds. 

Finally, you cannot set ``GRIST_RAISE_ERROR`` and ``GRIST_SAFEMODE`` 
in Gry: both values will default to ``N``.

Passing additional arguments to Requests.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

(This is advanced usage and you probably won't need it.)

In Pygrister, you may set ``GristApi.apicaller.request_options`` to a 
dictionary in order to pass optional arguments, not otherwise used by 
Pygrister, to the underlying Requests call. You can't do this in Gry, 
as you don't have direct access to the GristApi class. 

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

Please note that the above ``GRIST_GRY_TIMEOUT`` configuration may also be 
used to set a timeout for the Requests call. This is meant as a shortcut, 
as a timeout is almost always wanted. If a timeout is all you need, just 
set the config key. For anything more than this, you'll need a separate 
``gryrequest.json`` file. If a timeout setting is found in both places, 
``gryrequest.json`` will take precedence (if in neither place, Gry will 
default to 60 seconds anyway).

The ``gry conf`` command will output both the current Gry settings, and 
any Requests additional arguments you may have set. 

Common options.
---------------

All ``gry`` commands share, if appropriate, the following options.

Meta-content options.
^^^^^^^^^^^^^^^^^^^^^

- ``--help`` will display the online help content.

- ``-i``, ``--inspect`` will output some additional info on the command executed, 
  together with the result, eg. ::

      % gry doc see -i

  is the same as Pygrister's ::

      >>> grist.see_doc()
      >>> print(grist.inspect())

  This may be useful when a command fail with an Http error: just re-run it with 
  the ``-i`` option to find out what's going on.

Output type control.
^^^^^^^^^^^^^^^^^^^^

- ``-v``, ``--verbose`` will control the output provided by ``gry``:

  - when the option is not present (level 0, default), ``gry`` will print a nicely 
    formatted output, apt for human consumption;

  - pass ``-v`` once (level 1) to output the original Pygrister result instead: 
    note that this is a *printed Python object*. In other words, ::

      % gry doc see -v

    is the same as ::

      >>> status_code, result = grist.see_doc()
      >>> print(result)

  - pass the option twice (``-vv``, level 2) to output the original Grist API 
    response: note that this is a *json string*. In other words, ::

      % gry doc see -vv

    is *almost* the same as inspecting the content of the original Requests 
    response::

      >>> st, res = grist.see_doc()
      >>> print(grist.apicaller.response.text)

    (Except, it is really ``print(grist.apicaller.response_as_json()``, as 
    Gry has a dedicated function for this purpose, which puts a little extra 
    effort into returning valid json in some corner cases.)

    Retrieving the original json response may be useful for later parsing and 
    analysis:: 

      % gry doc see -vv > response.json

  The difference between the 3 output levels varies from command to command. 
  Note, however, that if the API call *fails* with a "bad" Http code, ``gry`` 
  (and Pygrister) will always return the original json response. Hence, ::

    % gry doc see -d bogus_doc
    % gry doc see -d bogus_doc -v

  will produce the same output.

- ``-q``, ``--quiet`` will suppress all output, always (overriding every 
  possible level of ``--verbose``). This may be helpful inside a script, 
  when you don't want to flood a log, etc. You can still inspect the 
  exit code to learn if the command succeeded::

    % gry doc new mynewdoc --workspace 0 -q  # bogus ws id
    % echo $?   # windows: echo %errorlevel%
    3

ID specification.
^^^^^^^^^^^^^^^^^

- ``-t``, ``--team`` ``<team_id>`` director the API call to the selected team ID, 
  instead of the one provided in your configuration;

- ``-w``, ``--workspace`` ``<ws_id>`` directs the API call to the selected workspace;

- ``-d``, ``--document`` ``<doc_id>`` directs the API call to the selected document.

Data type converters.
---------------------

(Please read the doc page about Pygrister converters, before you go on.)

Converters can be very helpful in ``gry``, especially in writing operations, 
because it's difficult to express anything other than strings in the command line.

If you want to include converters in your ``gry`` workflow, you must add a Python 
module named ``cliconverters.py`` *in your current directory* (in fact, you can put 
the file anywhere in your Python path, since ``gry`` will attempt to *import* it). 

Inside the file, write your converter functions as you need. You must, however, name 
the final converter dictionaries ``cli_out_converters`` and ``cli_in_converters``. 
These converters will be imported and applied to your ``gry`` call.

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
(and then some) before your command is parsed and executed, then shut down. 
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
