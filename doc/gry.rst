.. _gry_command_line:

The Gry command line tool.
==========================

``gry`` is the GRist pYthon cli tool (an acronym that 
`almost makes sense <https://xkcd.com/1460/>`_). It leverages the Pygrister 
library, mapping almost all the documented Grist APIs, and providing a clean, 
easy-to-remember interface in your system shell, with no need to load/learn 
Python.

This documentation page is intended for non-Python users: you don't have 
to know about Python to read this - you don't even have to browse through 
the rest of Pygrister's documentation, in fact. All you need is a basic 
understanding of your system shell. 

**Main features:**

- Gry maps almost all the Grist API, with only a few inevitable simplifications;
- 3 levels of output: you can choose between a nicely formatted summary for 
  human consumption, or the original Pygrister response, or even the underlying 
  Grist API retrieved response;
- easy to inspect: if a call goes wrong, just re-post it with the ``-i`` option 
  to take a peek under the hood; 
- online help everywhere: just add the ``--help`` option to sort it out;
- if you already work with Pygrister, you'll find that Gry accepts the same 
  :ref:`configuration files/variables<pygrister_configuration>`: 
  if you can post an api call via the ``GristApi`` class, then the 
  Gry cli will also work for you, out of the box;
- when you need a power boost, ``gry python`` opens a Python interpreter for you, 
  with Pygrister already configured and ready to use.

Basic usage goes as follows (where ``%`` is your shell prompt)::

    % gry team see  # get info on the "default" team, as per config
    % gry doc see   # the "default" document, as per config
    % gry doc see -d f4Y8Tov7TRkTQfUuj7TVdh  # select a specific document
    
    # if you need to switch to another document from now on: 
    % export GRIST_DOC_ID=f4Y8Tov7TRkTQfUuj7TVdh  # or "set" in windows
    % gry doc see  # same as above, but no need to add the "-d" option
    % gry doc see -d bogus_doc     # this will fail...
    % gry doc see -d bogus_doc -i  # ...so let's find out why 
    
    % gry ws see -w 42      # workspace info, in a nicely formatted table
    % gry ws see -w 42 -vv  # the same, in the original raw json
    
    % gry table new --help  # how do I add a table?
    % gry table new name:Text:Name age:Int:Age --table People  # like this!
    
    % gry col list -b People  # the columns of our new table
    % gry rec new name:"John Doe" age:42 -b People  # populate the table
    
    % gry sql "select * from People where age>?" -p 35  # run an sql query
    % gry python  # let's open a Python shell now!
    >>> gry.list_cols(table_id='People')  # "gry" is now a python object
    >>> exit()  # and we are back to the shell


Standalone distribution.
------------------------

Gry comes in two flavours: you may get it as a byproduct of installing 
the Pygrister library in your Python environment -- this is the option of 
choice for developers. 

Other users may prefer to grab the standalone distribution instead: this is 
a more convenient bundle including a Python runtime, the Pygrister library 
and Gry, in one single zip file. You won't need Python pre-installed on your 
computer. 

The standalone bundle is available for 
`download on GitHub <https://github.com/ricpol/pygrister/releases>`_. 
Get the "gry.zip" file and unpack it on your computer. Open your system shell, 
navigate to the directory where you unpacked the zip file, and type ``gry`` 
to start. 


Architecture and online help.
-----------------------------

Gry is organized in several "commands", which are *nouns* and refer to the various 
sections of the Grist API: we have ``gry doc``, ``gry table``, ``gry team`` 
and so on. Each command has several "sub-commands", which describe an action 
to perform (and are mostly *verbs*). Sub-commands tend to repeat across 
commands: ``gry doc new`` adds a document, ``gry table new`` adds a table, 
``gry col new`` adds a column, and so on.

Type ::

    % gry --help

to get a list of available commands. Then type, for instance, ::

    % gry doc --help

to list the sub-commands available for ``gry doc``. Finally, something like ::

    % gry doc new --help

will show you how to use a particular sub-command.

The only commands without a sub-command are 

- ``gry test`` performs a few sanity checks on your Grist setup, 
- ``gry conf`` prints your current Gry configuration,
- ``gry python`` opens a Grist-aware Python shell, 
- ``gry sql`` allows you to enter an Sql query directly, 
- ``gry version`` outputs Pygrister/Gry version.


Common options.
---------------

All ``gry`` commands share, if appropriate, the following options.

Meta-content options.
^^^^^^^^^^^^^^^^^^^^^

- ``--help`` will display the online help content.

- ``-i``, ``--inspect`` will output some additional info on the command executed, 
  together with the result. This may be useful when a command fail with an 
  Http error: just re-run it with the ``-i`` option to find out what's going on.
  
  If you know Pygrister, you will find that ::

      % gry doc see -i

  is the same as Pygrister's ::

      >>> grist.see_doc()
      >>> print(grist.inspect())

Output type control.
^^^^^^^^^^^^^^^^^^^^

- ``-v``, ``--verbose`` will control the output provided by ``gry``:

  - when the option is not present (level 0, default), ``gry`` will print 
    a nicely formatted output, apt for human consumption;

  - pass ``-v`` once (level 1) to output the original Pygrister result 
    instead. This will be a *printed Python object*. If you know Pygrister, 
    you will find that ::

      % gry doc see -v

    is the same as ::

      >>> status_code, result = grist.see_doc()
      >>> print(result)

  - pass the option twice (``-vv``, level 2) to output the original 
    Grist API response: note that this is a *json string*. In other words, ::

      % gry doc see -vv

    is *almost* the same as inspecting the content of the original Requests 
    response in Pygrister::

      >>> st, res = grist.see_doc()
      >>> print(grist.apicaller.response.text)

    (But not *quite*, as Gry will actually use 
    ``print(grist.apicaller.response_as_json()`` internally. In fact, Gry 
    has its own dedicated function for this purpose, which puts a little 
    extra effort into returning valid json in some corner cases.)

    Retrieving the original json response may be useful for later parsing and 
    analysis:: 

      % gry doc see -vv > response.json

  The difference between the 3 output levels varies from command to command. 
  Note, however, that if the API call *fails* with a "bad" Http code, ``gry`` 
  (and Pygrister) will always return the original json response. Hence, ::

    % gry doc see -d bogus_doc
    % gry doc see -d bogus_doc -v

  will produce the same output, since calling for "bogus_doc" will fail. 

- ``-q``, ``--quiet`` will suppress all output, always (overriding every 
  possible level of ``--verbose``). This may be helpful inside a script, 
  when you don't want to flood a log, etc. You can still inspect the 
  exit code to learn if the command succeeded::

    % gry doc new mynewdoc --workspace 0 -q  # silently fails, bogus ws id
    % echo $?                                # windows: echo %errorlevel%
    3

ID specification.
^^^^^^^^^^^^^^^^^

Gry will read from configuration files your default team/workspace/document 
ID, as we are about to see. However, you may also specify a different ID 
for the current Api call:

- ``-t``, ``--team`` directs the API call to the selected team ID, 
  instead of the one provided in your configuration;

- ``-w``, ``--workspace`` directs the API call to the selected workspace;

- ``-d``, ``--document`` directs the API call to the selected document.


Interactive prompt.
-------------------

Traditionally, in a cli program *arguments* are required, *options* like 
``--foo, -f`` should be... well, optional (ie., come with a default value). 
However, sometimes it makes sense having *required options* too - that is, 
asking for some *required* input using the more flexible *option* syntax. 
Although we try to keep this to a minimum, sometimes we can't avoid it. 
Consult the ``--help`` section of a command to find out if some options are, 
in fact, required. 

Every time an option is required, Gry also offers an *interactive prompt* for 
it: meaning, if you forget to fill in the option, Gry will give you a second 
chance instead of just crashing out. For example, ``gry table new`` syntax 
requires that you specify a ``--table`` option. If you forget, Gry will 
stop and prompt you for a table ID::

   % gry table new name:Text:Name age:Int:Age    # we miss a --table option
   Insert the table ID name:

This is the *only* use we make of interactive prompts, since Gry is not designed 
to be an interactive cli tool.

Please be extra careful with this feature: while it is meant to help you 
working in the shell, it could just hang indefinitely a *script*!


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
  returned a "bad" Http code (like 404, 500 and so on). Also, code ``3`` is 
  returned when the server was unreachable. This is almost never 
  Gry/Pygrister's fault, but likely a problem with your configuration: retry 
  the same command with the ``-i`` option to find out more. 

Of course, exit codes are seldom needed in normal interactive use, since the 
shell will let you know anyway; they could be more useful in batch scripts. 
To inspect the exit code, type ``echo $?`` or ``echo %errorlevel%`` depending 
on your shell.

Non-standard Http codes for connection errors.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When a connection error occurs, Pygrister will throw an exception 
(eg. ``ConnectionError``, ``Timeout``, ``InvalidURL``...) and crash out 
with a stacktrace message that may be useful for developers, but perhaps 
confusing for other users. Gry will make an effort to return 
a "normal" error message instead. For instance, if you try ``gry team see`` 
(a command that almost always succeeds) after shutting down your wifi, 
you'll get something like this::

  % gry team see
  Error! Status: 523 HTTPConnectionPool(...): Max retries exceeded with url ...

(Experienced users will note that we are faking a "bad" Http status code here, 
namely 523, even if, of course, this is not an Http error and there is no 
real status code to show. We borrow from Cloudflare some non-standard 
5xx codes they use to signal a connection error: you may get 523 "Origin Is 
Unreachable", 522 "Connection Timed Out", or 520 "Web Server Returned an 
Unknown Error", depending on the cases.)

A connection error will cause Gry to exit with status code ``3``, see above.


Configuration.
--------------

Gry will remember some configuration data for you, so that you don't have 
to type in all the boring details, like the api key, at every command. 

Gry configuration keys.
^^^^^^^^^^^^^^^^^^^^^^^

Gry will look for the following configuration keys (with their default 
values)::

  {
    "GRIST_API_KEY": "<your_api_key_here>",
    "GRIST_TEAM_SITE": "docs",
    "GRIST_WORKSPACE_ID": "0",
    "GRIST_DOC_ID": "<your_doc_id_here>",

    "GRIST_SELF_MANAGED": "N",
    "GRIST_SELF_MANAGED_HOME": "http://localhost:8484",
    "GRIST_SELF_MANAGED_SINGLE_ORG": "N"
  }

The first 4 keys are the most common and their meaning should be obvious. 
(:ref:`Here<grist_ids>` we explain the various Grist IDs more in detail, 
if you need a refresher.)

You must set the last 3 keys only if you intend to run Gry agains a self-managed 
version of Grist. In this case, set ``GRIST_SELF_MANAGED`` to ``Y``, 
then put the url of your Grist instance in ``GRIST_SELF_MANAGED_HOME``, 
and finally set ``GRIST_SELF_MANAGED_SINGLE_ORG`` to ``Y`` if you are running 
the single-org flavour of Grist. 

Where the Gry configuration is stored.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You may provide configuration via a json file, and/or setting environment 
variable in your shell session. 

Just put a json file called ``gryconf.json`` in the current working directory 
of your shell, and Gry will find and parse it. You may copy-paste the values 
above, and replace the defaults with something that makes sense for you.

**Standalone distribution**: if you are using the standalone bundle, you will 
find a ``gryconf.json`` file in the top-level directory of the distribution, 
ready for you to edit. The standalone Gry will use this file, *no matter the 
working directory* of your shell. 

You may also provide some (or all) configuration keys as environment variables 
in your shell. Env variables will *override* the corresponding keys in 
``gryconf.json``. It makes sense to use evn variables to temporary override 
your "normal" configuration for a while. For example, suppose you normally 
work with one Grist document: then you will fill in this document ID in 
``gryconf.json``. If you need to post just a few calls to another document, 
you don't have to edit the json file: an env variable will do the trick. ::

  % gry doc see    # the "default" doc, specified in gryconf.json
  % # now we need to work with another document...
  % export GRIST_DOC_ID=f4Y8Tov7TRkTQfUuj7TVdh  # windows: set GRIST_DOC_ID=...
  % gry doc see    # the other document!
  % # now we want to switch to our usual document again...
  % unset GRIST_DOC_ID    # windows: set GRIST_DOC_ID=
  % gry doc see    # the "default" doc again

Finally, remember that almost all Gry command also accept the ``-t``, 
``-w`` and ``-d`` options to temporary set team, workspace and document IDs, 
as seen above. 
These options will work for the current command only, of course. 

At any time, you may try ``% gry conf`` to print your current Gry configuration.

Differences with Pygrister configuration.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

(If you don't use Pygrister, you may skip this. Or, learn about 
:ref:`Pygrister configuration<pygrister_configuration>` before going on.)

While Gry will read configuration from its own ``gryconf.json`` file, in fact 
you may also use your Pygrister "static" configuration (``conf.json`` in your 
home directory, environment variables) if you already have it in place and 
working. In other words, if you can start a Python shell and just 
type in ``grist = GristApi(); grist.see_team()``, then ``gry`` will work too.

On the other side, ``gryconf.json`` is specific to ``gry``, and Pygrister will 
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

On top of the "static" configuration, ``gry`` commands accept common options 
to specify documents, teams, workspaces. These are, of course, the equivalent 
of ``GristApi`` optional arguments. For instance, this ::

    % gry doc see -d bbbf4Y8Tov7TRkTQfUuj7TVdhbb 

is the equivalent of Pygrister's ::

    >>> grist.see_doc(doc_id='f4Y8Tov7TRkTQfUuj7TVdh')

Gry accepts the same config keys as Pygrister, except that you cannot set 
``GRIST_RAISE_ERROR`` and ``GRIST_SAFEMODE`` in Gry: both values will 
default to ``N``.

Gry will accept an additional ``GRIST_GRY_TIMEOUT`` configuration key to set 
a timeout limit for the api call. This key is *optional*: if you don't provide 
a value, default will be 60 seconds. 
