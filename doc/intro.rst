Pygrister: a Python client for the Grist API.
=============================================

`Grist <https://www.getgrist.com/>`_ is a relational spreadsheet with tons of 
batteries included. The *Grist API* allows you to programmatically 
retrieve/update your data stored on Grist, and manipulate most of the basic 
Grist objects, such as workspaces, documents, user permissions and so on. 

Pygrister is a basic Grist client that covers all the documented APIs. 
Pygrister keeps track of certain configuration for you, remembering your 
team site, workspace, working document, so that you don't have to type in 
the boring stuff every time. Apart from that and little else, Pygrister 
is rather low-level: usually, it will call the api and retrieve the response 
"as is". 
If the api call is malformed, you will simply receive a bad HTTP status code. 

In addition, Pygrister will not attempt to convert sent and received data types: 
however, it will execute custom converter functions, if provided.

This document covers the basic Pygrister concepts, patterns and configurations. 
However, the api call functions themselves are not documented in Pygrister: 
see the 
`Grist API reference documentation <https://support.getgrist.com/api/>`_ 
for details about each api signature, and browse the Pygrister test suite 
for more usage examples.


The many Grist IDs, explained. 
------------------------------

Before discussing Pygrister, we need to learn how Grist identifies the various 
object of its own data model: 

- First of all, there is the **API key**: this is needed to access the APIs, 
  and must be kept secret. You can find it in your 
  `Account Settings page <https://apitestteam.getgrist.com/account>`_.
- Your **Team Site** is where your *workspaces* live; you may have more than one, 
  and you own at least your "personal site" ("@my-name"). You may create 
  a new site by clicking on the top left dropdown list and selecting 
  "Create new team site". The site ID is actually the *subdomain* of your 
  Grist url: if your site is available at ``https://myteam.getgrist.com``, 
  then your site ID is ``myteam``. Please note that you can choose a different 
  *name* for your team: the team ID will be the subdomain, anyway. 
  Your "personal site" ID is always ``docs``.
- **Workspaces** are where the *documents* live: you may have more than one 
  workspace for each of your team sites. When you create a new site, you will 
  start with a first workspace named "Home": most of the times, you won't need 
  more. The available workspaces are listed in the left column of the Grist 
  site; to create a new workspace, clic on the "Add new" green button. The 
  workspace ID is *an integer number*, and it is shown in the Grist url. 
  If you clic on one of the workspaces listed on the left column, you will be 
  directed to a page like ``https://myteam.getgrist.com/ws/12345/``: hence, 
  your workspace ID is ``12345``. Again, workspaces do have *names*, but all 
  that matters is their numerical ID. 
- The **Document** is, basically, your database: a collection of *tables*, 
  widgets, specific user permissions and configuration. You may have multiple 
  documents in your workspace. To create a document, clic on the "Add new" 
  green button. You can find your document ID by clicking on "Settings" in the 
  (lower) left column. The ID is a long alphanumeric string like 
  ``1asxv4ZYLGPtJ6UDgN1z8Q``.
- A **Table** is... well, a table: where the actual data is stored. Of course, 
  you may have multiple tables in a document. The table ID is usually its name 
  but again, you can also customize the table's name. The best way to find out 
  all your table IDs, is to clic on "Raw data" in the left column: for each 
  table, a "TABLE ID" will also be shown. Please note: table IDs will always 
  start with a *capital* letter. If you give a table a name starting with a 
  number, Grist will leave the name as you prefer, then silently add a "T" 
  in front of the ID. If the table's name starts with a lowercase letter, 
  Grist will capitalize it in the corresponding ID. 
- Tables are made up of **Columns**, of course. Each column will have a *label* 
  and a "real name", the ID. You can find both in the right column of the Grist 
  screen, under "COLUMN LABEL AND ID". Usually, the label and ID will be the 
  same, but you may choose otherwise. Again, a Column ID must start with a 
  letter (here, lowercase is ok): if the name starts with a number, Grist will 
  prepend a "c" to the corresponding ID. 
- The **Rows** are instances of your data. You may assign your rows a "custom" 
  id, but it will have no meaning to the Grist API. The only "real ID" that 
  matters is a unique integer number that Grist silently adds to each row. 
  This real ID is stored in a hidden ``id`` column. Hence, is it not a good 
  idea to have one of your columns also called "id": if you try, Grist will 
  leave "id" as the *label* of the column, but silently change the name itself 
  to "id2", which may be confusing. You cannot change the Grist ``id`` column, 
  and it's not easy to show it either: you can create a formula column and set it 
  to ``=$id``, or you can just download the underlying Sqlite database and 
  take a look under the hood. Retrieving rows via the APIs will also give you 
  their IDs. 
- Finally, **Attachments** are a bit of an oddball. The file itself, once 
  uploaded, is assigned a numerical ID that is global to your document. 
  An attachment-type column, then, really stores only the file ID. 
  Figuring out the attachment ID of a file is not straightforward: if you 
  have an attachment column named "A", you may create a formula column and 
  set it to ``=$A`` - or, download the Sqlite database. 


The ``GristApi`` class.
=======================

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

There are many API call functions: it may help knowing that almost all of 
their names follow this pattern:

- ``list_*`` functions implement ``GET`` calls to retrieve object lists;
- ``see_*`` functions implement ``GET`` calls to retrieve one particular 
  object;
- ``update_*`` functions implement ``PATCH`` calls to modify an object attributes; 
- ``add_*`` functions implement ``POST`` calls to add an object;
- ``add_update_*`` functions implement ``PUT`` calls to modify an object 
  if existing, adding otherwise;
- ``delete_*`` functions implement ``DELETE`` calls to delete an object 
  (note: delete functions will always ask explicitly for the object ID to 
  be deleted, as a safety measure);
- ``download_*`` functions are for downloading.

The docstring of each function reports the underlying Grist API: consult the 
`Grist API reference documentation <https://support.getgrist.com/api/>`_ 
for details about each API signature, and browse the Pygrister test suite 
for more usage examples.

API call return values.
-----------------------

API call functions always return a 2-items tuple: the *Http status code* of the 
response (an integer number), and the *response body*. Pygrister makes an 
effort to simplify a little and uniform the json objects returned by the 
underlying Grist Api. Responses returned by Pygrister will follow this pattern: 

- all ``see_*`` functions will return a dictionary, describing a single object 
  (one table, one column...);
- all ``list_*`` functions will return a list of dictionaries;
- "singular form" ``add_*`` functions (``add_workspace``, ``add_doc``) will 
  return the ID of the added object;
- "plural form" ``add_*`` functions (``add_tables``...) will return a list of 
  IDs of the added objects (possibly just one);
- ``delete_*``, ``update_*``, ``add_update_*`` functions will return ``None``; 
  ``download_*`` functions will return ``None`` and download something as a 
  side effect. 

Docstrings in each function report the return type, but you'll still need the 
Grist API documentation for the details. 

Pygrister will also save the original response body of the last API call anyway: 
if you need it, inspect the ``resp_content`` attribute before making another call::

    >>> grist = GristApi()
    >>> grist.add_cols('Table1', [{'id': 'colA'}, {'id': 'colB'}])
    (200, ['colA', 'colB'])
    >>> grist.resp_content # the original reponse, a little more nested!
    "{'columns': [{'id': 'colA'}, {'id': 'colB'}]}"

In addition, API call functions may throw an exception if something went wrong. 
This, however, is a matter of configuration: you may choose to inspect 
the status code instead. For this and other configuration options, read on. 

Record format in Pygrister.
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Pygrister puts extra effort into uniforming the APIs for record manipulation. 
The original Grist API has a few ways to describe a list of records, depending 
on the case. In Pygrister, a record is *always* a ``{col: value}`` dictionary, 
and a list of records is a ``list[dict]``. This is true for both input parameters 
and return values.  

A "Pygrister record" may or may not include record IDs (that is, the special 
hidden ``id`` column operated by Grist, see above). For example, you'll need to 
include IDs when you are updating existent records::

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

Grist IDs in Pygrister functions.
---------------------------------

Browsing the Pygrister API call functions, you will find many optional 
``*_id`` parameters, mapping to the Grist IDs detailed above. Parameter 
names follow this pattern:

- ``team_id`` refers to the Grist team ID (subdomain);
- ``ws_id`` is the numerical Workspace ID;
- ``doc_id`` is the Document ID;
- ``table_id`` is the Table ID;
- ``attachment_id`` is the Attachment ID.
