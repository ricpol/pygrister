An overview of the ``GristApi`` class.
======================================

At the heart of Pygrister is the ``GristApi`` class, exposing all the Grist 
API functions. Basic usage is very straightforward::

    from pygrister.api import GristApi

    grist = GristApi()
    # list users/permissions for the current document
    status_code, response = grist.list_doc_users()
    # fetch all rows in a table
    status_code, response = grist.see_records('Table1') 
    # add a column to a table
    cols = [{'id': 'age', 'fields': {'label':'age', 'type': 'Int'}}]
    status_code, response = grist.add_cols('Table1', cols) 

There are many API call functions (ie, methods of a ``GristApi`` instance): 
it may help knowing that almost all of their names follow this pattern:

- ``list_*`` functions implement ``GET`` calls to retrieve object lists;
- ``see_*`` functions implement ``GET`` calls to retrieve one particular 
  object;
- ``update_*`` functions implement ``PATCH`` calls to modify an object; 
- ``add_*`` functions implement ``POST`` calls to add an object;
- ``add_update_*`` functions implement ``PUT`` calls to modify an object 
  if existing, adding otherwise;
- ``delete_*`` functions implement ``DELETE`` calls to delete an object;
- ``download_*`` functions are for downloading.

The :ref:`docstring of each function<gristapi_docstrings>` reports the 
underlying Grist API: consult the 
`Grist API reference documentation <https://support.getgrist.com/api/>`_ 
for details about each API signature, and browse the Pygrister test suite 
for more usage examples.


API call return values.
-----------------------

API call functions always return a 2-items tuple: 

- the *Http status code* of the response (an integer number), and 
- the *response body* (a different Python object, depending on the Api called). 

In addition, a function may throw a 
`Requests exception <https://requests.readthedocs.io/en/latest/api/#exceptions>`_ 
in case of connection failure. 

Even if a connection responds, a ``requests.HTTPError`` may still occurr when the 
Http status code is "bad" (ie, 300+). However, you may turn off this behaviour, 
:ref:`as we will see<errors_statuscodes>`. 

Usually, the response part of the returned tuple will be the Python equivalent 
of the json structure received from the Api call. Only sometimes, 
Pygrister will put a little effort in simplifying and uniforming the 
underlying Grist Api. However, Pygrister will always store the original 
response body as well: if you need it, inspect the ``GristApi.apicaller.response`` 
attribute *before* making any subsequent Api call::

    >>> grist = GristApi()
    >>> grist.add_cols('Table1', [{'id': 'colA'}, {'id': 'colB'}])
    (200, ['colA', 'colB'])
    >>> grist.apicaller.response # the original reponse, a little more nested!
    "{'columns': [{'id': 'colA'}, {'id': 'colB'}]}"

``GristApi.apicaller.response`` is part of Pygrister's inspecting and 
troubleshooting utilities: we will take a deeper look at this 
:ref:`later on<inspecting_api_call>`. 

As a general rule, responses returned by Pygrister follows this pattern: 

- all ``see_*`` functions return a dictionary, describing a single object 
  (one table, one column...);
- all ``list_*`` functions return a list of dictionaries;
- "singular form" ``add_*`` functions (as in ``add_workspace``, ``add_doc``) 
  return the ID of the added object;
- "plural form" ``add_*`` functions (``add_tables``...) return a list of 
  IDs of the added objects (possibly just one);
- ``delete_*``, ``update_*``, ``add_update_*`` functions return ``None``; 
  ``download_*`` functions return ``None`` and download something as a 
  side effect. 

Docstrings in each function report the return type of the response, 
but you'll still need the Grist API documentation for the details. 


Grist IDs in Pygrister functions.
---------------------------------

Browsing the Pygrister API call functions, you will find many optional 
parameters named ``*_id``, mapping to the :ref:`Grist IDs<grist_ids>`. 
As a general rule, parameter names follow this pattern:

- ``team_id`` refers to the Grist team ID (subdomain);
- ``ws_id`` is the numerical Workspace ID;
- ``doc_id`` is the Document ID;
- ``table_id`` is the Table ID;
- ``attachment_id`` is the Attachment ID.


Record format in Pygrister.
---------------------------

Pygrister puts extra effort in uniforming the APIs for record manipulation. 
The original Grist API has a few ways to describe a list of records, depending 
on the case. In Pygrister, a record is *always* a ``{col: value}`` dictionary, 
and a list of records is a ``list[dict]``. This is true for both input parameters 
and return values.  

A "Pygrister record" may or may not include record IDs (that is, the special 
hidden ``id`` column operated by Grist, as we know). 
For example, you'll need to include IDs when you are updating existent records::

    >>> grist = GristApi()
    >>> records = [{'A': 'foo', 'B': 'bar'}, {'A': 'baz'}] # no IDs
    >>> grist.add_records('Table1', records)
    (200, [1, 2])
    >>> to_update = [{'id': 2, 'B': 'foobar'}] # records with IDs
    >>> grist.update_records('Table1', to_update)
    (200, None)
    >>> grist.list_records('Table1')
    (200, [{'id': 1, 'A': 'foo', 'B': 'bar'}, {'id': 2, 'A': 'baz', 'B': 'foobar'}])
    >>> grist.resp_content # the underlying Grist API format
    "{'records': [{'id': 1, 'fields': {'A': 'foo', 'B': 'bar'}}, 
                  {'id': 2, 'fields': {'A': 'baz', 'B': 'foobar'}}]}"

Note that you don't have to fill in all the values in a record, as demonstrated  
in the first example above.
