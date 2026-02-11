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

While Pygrister will not attempt to guess and convert types, it will execute 
your custom :ref:`converter functions<converter_functions>`, if provided.

This document covers the basic Pygrister concepts, patterns and configurations. 
However, the api call functions themselves are *not* documented in Pygrister: 
consult the 
`Grist API reference documentation <https://support.getgrist.com/api/>`_ 
for details about each api signature, and browse the Pygrister test suite 
for more usage examples.


.. _grist_ids:

The many Grist IDs, explained. 
------------------------------

Before discussing Pygrister, we need to learn how Grist identifies the various 
objects in its own data model: 

- First of all, there is the **API key**: this is needed to access the APIs, 
  and must be kept secret. You can find it in your 
  `Account Settings page <https://apitestteam.getgrist.com/account>`_.
- Your **Team Site** is where your *workspaces* live; you may have more than one, 
  and you own at least your "personal site" ("@my-name"). The site ID is actually 
  the *subdomain* of your Grist url: if your site is available at 
  ``https://myteam.getgrist.com``, then your site ID is ``myteam``. 
  Please note that you can choose a different *name* for your team: the 
  team ID will be the subdomain, anyway. 
  Your "personal site" ID is always ``docs``.
- **Workspaces** are where the *documents* live: you may have more than one 
  workspace for each of your team sites. The workspace ID is *an integer number*, 
  and it is shown in the Grist url, eg. ``https://myteam.getgrist.com/ws/12345/``. 
  Again, workspaces do have *names*, but all that matters is their numerical ID. 
- A **Document** is, basically, your database: a collection of *tables*, 
  widgets, specific user permissions and configuration. You may have multiple 
  documents iside a workspace. The ID is a long alphanumeric string like 
  ``1asxv4ZYLGPtJ6UDgN1z8Q``.
- A **Table** is... well, a table: where the actual data is stored. Of course, 
  you may have multiple tables in a document. The table ID is usually its name 
  but again, you can also customize the table's name. Please note: table IDs 
  will always start with a *capital* letter. If you start a table name with a 
  number, Grist will leave the apparent name, then silently add a "T" 
  in front of the ID. If the table's name starts with a lowercase letter, 
  Grist will capitalize it in the corresponding ID. 
- Tables are made up of **Columns**, of course. Each column will have a *label* 
  and a "real name", the ID. Usually, the label and ID will be the 
  same, but you may choose otherwise. Again, a Column ID must start with a 
  letter (lowercase is ok): if the name starts with a number, Grist will 
  prepend a "c" to the corresponding ID. 
- The **Rows** are instances of your data. You may assign your rows a "custom" 
  id, but it will have no meaning to the Grist API. The only "real ID" that 
  matters is a unique integer number that Grist silently adds to each row. 
  This real ID is stored in a hidden ``id`` column. Hence, is it not a good 
  idea to have one of your columns also called "id": if you try, Grist will 
  leave "id" as the *label* of the column, but silently change the name itself 
  to "id2", which may be confusing. You cannot change the Grist ``id`` column, 
  and it's not easy to show it either: you can create a formula column and set 
  it to ``=$id``, or just download the underlying Sqlite database and 
  take a look under the hood. Retrieving rows via the APIs will also give you 
  their IDs. 
- Finally, **Attachments** are a bit of an oddball. The file itself, once 
  uploaded, is assigned a numerical ID that is global to your document. 
  An attachment-type column, then, really stores only the file ID. 
  Figuring out the attachment ID of a file is not straightforward: if you 
  have an attachment column named "A", you may create a formula column and 
  set it to ``=$A`` - or, download the Sqlite database. 
- Users have their own IDs too, which is an integer number. 
  The new :ref:`SCIM apis<scim_apis_support>` will make use of users IDs: 
  however, SCIM is not enabled (so far) in the regular SaaS Grist, and 
  you can't retrieve the "home" database where those IDs are stored. 
  See the SCIM section of this documentation for more info. 
  The few, non-SCIM apis dealing with user manipulation identify users 
  by their own unique email. 
