.. _scim_apis_support:

Support for the Grist SCIM apis.
================================

Grist introduced support for the SCIM standard apis for managing users, back in 
`version 1.3.2 <https://github.com/gristlabs/grist-core/releases/tag/v1.3.2>`_. 
Even if the Grist SCIM apis are still at an early stage of developement, 
we decided to mirror them in Pygrister. A fair warning: both the Grist apis 
and Pygrister's rendition are experimental and likely to change. 

This is a *provisional* doc page for our Pygrister SCIM support, that 
leaves quite a few points unresolved: we will update this page as the Grist 
apis (and our own understanding) will evolve. 

You may learn about the Grist SCIM apis browsing their official 
`documentation <https://support.getgrist.com/install/scim/>`_. 


SCIM is not for everyone.
-------------------------

First of all, SCIM is not even enabled on the "regular" SaaS Grist (that 
is, www.getgrist.com). If you want to try out SCIM, you must set up a local 
installation and enable SCIM (set ``GRIST_ENABLE_SCIM`` in your environment). 

(Note: you will find a new SCIM section in your Api console, but you can't 
actually post a call if you are on SaaS Grist.)

Be careful! If you already run your own Grist service, please *do not* run 
the Pygrister test suite against the same instance that you use for everyday's 
work: always set up a separate, disposable container for testing. 
This is because our test suite will create many users, that you can't easily 
delete afterwards. 


Sometimes, SCIM is different.
-----------------------------

While testing the Grist SCIM apis ourselves, we found quite a few rough 
edges: sometimes we tried to accomodate, sometimes we just couldn't figure 
it out. For instance, and in no particular order: 

- the apis will accept user IDs as *integers*, return them as *strings*:  
  we always use integers;
- when creating or updating 
  `a user <https://support.getgrist.com/api/#tag/scim/operation/createUser>`_, 
  protocol for providing emails and pictures is rather convoluted and support 
  multiple instances: in reality, Grist will only store the "primary" email/pic. 
  It's easier in Pygrister: you just provide a list of strings for both emails and 
  pics: the first one is intended as the primary (then again, only the first 
  item will be used by Grist anyway); 
- the DELETE endpoint will only return a status code, with no payload. This 
  is an exception (perhaps an oversight?) to the behaviour of Grist apis, 
  which always return some kind of content. The corresponding api in 
  Pygrister will return ``None``, like every other ``delete_*`` function; 
- we couldn't make bulk operations work: the api call itself goes through, 
  but then every single operation will fail because the "path" component 
  appears to be wrong. Maybe it's just us... if anyone figures this our, 
  please let us know!
  (Also, please note that Pygrister's ``bulk_users`` will return a list of the 
  status codes for every single operation, to simplify the underlying Grist 
  api. To check the "real" response, inspect ``grist.resp_content`` as usual.)
- we couldn't make filters work in the 
  `getUsers endpoint <https://support.getgrist.com/api/#tag/scim/operation/getUsers>`_,  
  while they seem to work just fine in the 
  `search case <https://support.getgrist.com/api/#tag/scim/operation/searchUsers>`_. 
  See also the relevant code in our test suite. 

If you are interested in testing the Grist SCIM apis with Pygrister, you are 
most welcome: please be advised that it might be difficult to tell whether 
a problem is with the Grist apis or Pygrister's code. You should always 
double-check you call with the Grist Api console, before filing a bug report 
to the wrong place!


What about the old user-related apis?
-------------------------------------

Existing endpoints that already deal with user creation, like 
``update_team_users``, ``update_workspace_users`` and ``update_doc_users`` 
(using their Pygrister names) will work as before, of course. However, 
they are somewhat limited, in that they create a user and set permissions 
in one single step, but you can't fill in all the user's details. 

Theoretically, you should first add the user with the SCIM api, and only 
then add her to the team/workspace/document. But we don't know what the 
Grist team has in store for these non-SCIM user endopoints. Maybe at some 
point they will stop working for user creation altogether. 

You may experiment with the difference between SCIM and non-SCIM user creation 
by directly inspecting the ``home.sqlite3`` database in your 
local installation's data folder (the home db is not accessible in SaaS Grist).


Wait, did you say pagination?!
------------------------------

Two of the new Grist SCIM endpoints (namely, 
`getUsers <https://support.getgrist.com/api/#tag/scim/operation/getUsers>`_ 
and
`searchUsers <https://support.getgrist.com/api/#tag/scim/operation/searchUsers>`_)  
support *pagination*: you also pass a starting point and a number of users 
to be retrieved with one single call.

While these are the only "paginated" endpoints in the Grist apis right now 
(and, realistically, the number of users is rarely high enough to need this), 
we cannot exclude that there are plans to introduce pagination in other places 
at some point. 

Thus, we made a little extra effort in supporting pagination in a smoother, 
more pythonic way. With any luck, the mechanism will also adapt to future 
paginated apis, if they arrive. However, keep in mind that 
this part is still very unstable and experimental, and may change in the future. 

**The rule is**: every Grist endpoint (say, ``fooapi``) that support pagination 
always has *two* corrisponding functions in the ``GristApi`` class: 

- a ``GristApi.fooapi_raw`` function, that calls ``fooapi`` in the traditional 
  way, without any "fancy" pagination. You just submit your starting point and 
  number of items to be retrieved, and the function will return the usual 
  ``status_code, result`` tuple, just like all the other Pygrister apis. If 
  you then want the next chunk of results, you'll have to make another call to 
  ``fooapi_raw``, submitting the next starting point, and so on. 
  **Please note**: all ``GristApi`` functions ending in ``*_raw`` will always 
  return the response "as it is" from the Grist api call (ie, a dictionary). 
  This is an exception to the usual Pygrister 
  `naming convention <https://pygrister.readthedocs.io/en/latest/intro.html#api-call-return-values>`_: 
  for instance a ``list_fooapi_raw`` function will return a single dictionary, 
  not a list. 

- a ``GristApi.fooapi`` function, dealing with the api the "fancy" way, with 
  auto-pagination. These functions will *not* return the usual ``status_code, 
  result`` tuple, but instead a Python *iterable object*, that you 
  can transverse like a normal Python iterable. Each time you call ``next()`` on 
  it, the iterable will in turn post the api call for you, and return the 
  ``status_code, result`` tuple; the internal indexes will be automatically 
  updated. 

An example will clarify. ``GristApi.list_users`` is a "paginated" api 
(and ``list_users_raw`` is the corresponding traditional function). 
Let's see it at work:: 

    >>> from pygrister.api import GristApi
    >>> grist = GristApi(...)
    >>> userlist = grist.list_users(start=1, chunk=5)  # (1)
    >>> status_code, result = next(userlist)           # (2) 
    >>> status_code, result = next(userlist)           # (3)
    >>> # and so on, until... 
    >>> status_code, result = next(userlist)           # (4)
    ...
    StopIteration


In ``(1)``, we call the ``GristApi`` "paginated" function. Note that at, 
this point, no actual api call has been posted yet: ``userlist`` is just 
an "empty" iterable. Then, in ``(2)``, we start iterating. Now the 
first api call is posted, and the result is retrieved. Hopefully, the 
status code will be 200 and ``result`` will have the first batch of 5 
users. At the next iteration, in ``(3)``, a new api call will be placed, 
with the updated index, retrieving the next 5 users, and so on. 
When there are no more users to retrieve, a ``StopIteration`` will be raised 
(this is the normal way in Python). 

Of course, you don't have to keep calling ``next``. As with any regular 
Python iterable, you want to use a ``for`` loop:: 

    >>> userlist = grist.list_users(start=1, chunk=5)
    >>> for status_code, result in userlist:
    ...     print(result) # or whatever

Pretty neat, right? At every step of the loop, the api call will be posted 
and the result retrieved. But wait, there's more!

*After* the first call has been posted, the iterable will have a ``__len__`` 
attribute storing the total number of items::

    >>> userlist = grist.list_users(start=1, chunk=5)
    >>> len(userlist)  # we can't know just yet
    0
    >>> st, res = next(userlist)
    >>> len(userlist)  # now this is the total number we are going to retrieve
    42

You can still maintain control of the fine-tuning, even when using the 
iterable object: the attributes ``index`` and ``items`` have the current 
index and the number of items to retrieve, and you may change them as you 
iterate. For example, this trick will repeat the last item of the previous 
chunk (useful sometimes in real-life pagination)::

    >>> userlist = grist.list_users(start=1, chunk=5)
    >>> for status_code, result in userlist:
    ...     print([i['id'] for i in result])
    ...     userlist.index -= 1 # move the index back one
    ...
    [1, 2, 3, 4, 5]
    [5, 6, 7, 8, 9]
    [9, 10]

Another interesting feature to keep in mind: the iterable object is just a 
thin wrapper, but the actual api call is still managed by the ``GristApi`` 
instance as usual. This means that all the usual goodies are still available, 
just like for any other api call. For instance, if you get a bad status code 
while iterating, you can still ``inspect`` the ``GristApi`` instance to find out 
what happened::

    >>> userlist = grist.list_users(start=1, chunk=5)
    >>> st, res = next(userlist)
    >>> # now, say the server crashes... 
    >>> st, res = next(userlist)
    ...
    HTTPError
    >>> print(grist.inspect()) # GristApi will know!

Of course, for now we have only 2 "paginated" apis (``list_users`` and 
``search_users``, with the corresponding ``list_users_raw`` and 
``search_users_raw``) and they both deal with the niche SCIM interface, 
so all of this probably won't do you any good in everyday life... but maybe 
in the future!

Finally, there is still one oddity (a bug, perhaps?) in the Grist apis 
that you should be aware of. When you pass an out-of-range index to a 
"paginated" api, you will still retrieve the first items as if nothing. 
You can test this in Pygrister too, using the ``*_raw`` function that mirrors 
the original api behaviour::

    >>> st, res = grist.list_users_raw(start=1, chunk=5) # the first 5 users
    >>> st, res = grist.list_users_raw(start=100000, chunk=5) # still the first 5 users!

This is annoying: when you iterate manually, you risk cycling over and over, 
because you'll never get an empty set of results. Keep an eye on the total 
number of items to know when to stop. Of course, our fancy iterable object 
already keeps track for you behind the scenes, so you won't have this 
problem if you use it instead. 
