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

Python version required.
------------------------

Pygrister will work with any Python>=3.9. 

Note that Grist itself may have 
`stricter Python requirements <https://support.getgrist.com/python/#supported-python-versions>`_ 
but don't mix things up: the Grist's Python lives on the server, supporting 
a Grist instance. You will likely run Pygrister from a client instead, with 
your Python of choice. 

Install.
--------

Right now, Pygrister is in beta stage, meaning that the overall interface 
should be fairly stable but I still make no promises about further changes. 

You can install Pygrister from PyPI::

    python -m pip install pygrister

Note that this repo may have recent features not yet released on PyPI: 
see ``NEWS.txt`` and/or the commit history. To try the "bleeding edge" 
from GitHub::

    python -m pip install git+https://github.com/ricpol/pygrister

What's next.
------------

- Add support for some other useful, *undocumented* Grist Apis; 
- Maybe write a few "macros/recipes" for common Grist tasks... 

Any feedback and contribution is *very welcome* at this stage! 

License.
--------

Pygrister is released under the MIT license (see ``LICENSE.rst``). 
Copyright 2024-2025 Riccardo Polignieri
