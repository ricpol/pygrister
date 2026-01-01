Pygrister: a Python client for the Grist API.
=============================================

`Grist <https://www.getgrist.com/>`_ is a relational spreadsheet with tons of 
batteries included. The `Grist API <https://support.getgrist.com/api>`_ 
allows you to programmatically retrieve/update your data stored on Grist, 
and manipulate most of the basic Grist objects, such as workspaces, documents, 
user permissions and so on. 

Pygrister is a Grist client that covers all the documented APIs. 
Pygrister keeps track of basic configuration for you, remembering your 
team site, workspace, working document, so that you don't have to type in 
the boring stuff every time. Apart from this and little else, Pygrister 
is rather low-level: it will call the api and retrieve the response, with 
only minor changes. 
If the api call is malformed, you will simply receive a bad HTTP status code. 

Basic usage goes as follows::

    from pygrister.api import GristApi

    grist = GristApi()
    # list users/permissions for the current document
    status_code, response = grist.list_doc_users()
    # fetch all rows in a table
    status_code, response = grist.list_records('Table1') 
    # add a column to a table
    cols = [{'id': 'age', 'fields': {'label':'age', 'type': 'Int'}}]
    status_code, response = grist.add_cols('Table1', cols) 

You should `read the docs first <https://pygrister.readthedocs.io>`_, 
and then take a look at the test suite for more usage examples. 

Gry: the Grist cli tool.
------------------------

Gry is a command line tool to query the Grist Api. Gry is based on Pygrister, 
but you can use/vendor it as a stand-alone tool, with no prior Python/Pygrister 
knowledge needed. 

Gry is installed with Pygrister: to try it out, just type ::

    % gry --help    # % is your shell prompt

and find out what Gry can do for you (or, read the online documentation!).

Basic usage goes as follows::

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


Python version required.
------------------------

Pygrister (and Gry) will work with any Python>=3.9. 

Note that Grist itself may have 
`stricter Python requirements <https://support.getgrist.com/python/#supported-python-versions>`_ 
but don't mix things up: the Grist's Python lives on the server, supporting 
a Grist instance. You will likely run Pygrister from a client instead, with 
your Python of choice. 

Install.
--------

Any feedback and contribution is *very welcome* at this stage! 

Right now, Pygrister is in beta stage, meaning that the overall interface 
should be fairly stable but I make no promises about further changes. 
The new Scim api support is still *very* experimental. 

You can install Pygrister from PyPI::

    python -m pip install pygrister

Note that this repo may have recent features not yet released on PyPI: 
see ``NEWS.txt`` and/or the commit history. To try the "bleeding edge" 
from GitHub::

    python -m pip install git+https://github.com/ricpol/pygrister

License.
--------

Pygrister/Gry is released under the MIT license (see ``LICENSE.rst``). 
Copyright 2024-2026 Riccardo Polignieri
