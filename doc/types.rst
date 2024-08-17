Type checking and converting.
=============================

Types in Grist can be tricky. Grist makes use of Sqlite for data storage 
which, as it is well known, does not enforce data types in columns (it has 
a notion of `type affinity <https://www.sqlite.org/datatype3.html>`_ of its 
own, however).

This is intended as a feature in Grist, which is modeled more like a spreadsheet 
that a traditional database: you may put a note like "???" or "ask Mark" into an 
integer cell, and Sqlite won't complain about type consistency. Grist itself 
will take advantage of its more relaxed type system to store errors in formula 
columns, and so on. 

The flip of the coin is that it is difficult, bordering impossible, to enforce 
type consistency in Grist. Of course, as long as you only insert data via the 
APIs (and/or Pygrister!), you can triple-check your inputs; but then, you can't 
prevent a GUI user from inserting whatever they want, basically. True, you may 
deny write permissions to GUI users, but... then what's the point of using Grist? 
Bottom line, if you are looking for a strict type system, perhaps Grist is not 
the tool for you. 

To complicate matters further, it must be said that Grist's type system is not 
without its own quirks. Sometimes it's because the Sqlite type affinity comes 
into play. For instance, if you put a *numerical string* into an integer column 
(say, ``INSERT INTO mytable (myint) VALUES ("42");``) Sqlite will happily 
convert it for you: thus, the same applies if you try this with the Grist APIs. 

Sometimes, Grist will override the Sqlite default behaviour: for instance, you 
can't put a float into an integer column, neither with the GUI nor with the API, 
even if Sqlite would allow that. 

And sometimes, the GUI and the API will behave in a subtly different way. 
For instance, a Grist "date" is stored as an integer in Sqlite. In fact, if you 
use the API, you should pass an integer timestamp. However, if you just write  
a number in the GUI cell, that will be treated as *text*, since you didn't 
use the widget to select a date... but wait! You can't actually store a 
*numerical string* in an integer Sqlite column, because it will be converted 
(and thus interpreted as a timestamp). To circumvent Sqlite type affinity, 
Grist will silently convert any *numerical string* in a *date* column to an 
*exadecimal blob* and store it in this format. As a result, you can put 
a number in a date column using the GUI, but not with the API. (The same goes 
with a boolean column.)

There are many of these undocumented quirks and it is difficult to keep up 
with them all. On top of this, also your needs and use cases will vary. 
Sometimes you'll need a type check just for a few columns, instead of the 
whole table; sometimes it's ok to have the occasional string, or Null value 
inserted, and so on. 

This is why Pygrister declines to check and/or convert types for you. 
Instead, Pygrister will offer a hook to execute custom converter functions, 
that you can tailor to your needs. 

Converter functions.
--------------------

A converter function is simply a function that accepts a single argument and 
returns a single value.

You may write both "input converters" (for data that you are about to write 
to the database) and "output converters" (for data that you are pulling 
from the database).

Given the relaxed nature of Grist/Sqlite type system, you are not required to 
be consistent about the types returned by your converters. Something like this 

:: 

    def maybe_to_int(value): 
        try:
            res = int(value)
        except:
            return None
        if res == 42:
            return "the answer"
        return res

could totally work as an input converter for an integer column in Grist. 

On the other hand, keep in mind that input converters should return, at the 
very least, something that you can safely pass to the Grist API, i.e. a 
json-izable value. For instance, if you need to store in Grist an exact 
decimal number, you can't have your converter simply return a ``decimal.Decimal`` 
instance (no more that you could pass it directly to the API!). You may want 
to return ``Decimal.to_eng_string`` instead, and store the value as a string.

Also note that input converters are applied *before* calling the API, 
of course: Pygrister has no say in any further mangling of your data, once 
the converted values are passed to the API. For instance, as discussed above, 
you can store a *string* into a Date column, but not a *numerical string* 
(at least, not with the API). Hence, if you have an input converter for a 
Date column which may return numerical strings, keep in mind that your values 
will still be converted to *integers* by Sqlite, then interpreted as *dates* by 
Grist, which may not be the way you intended. (A solution would be returning 
a *hex blob* instead, replicating the marshalling algorithm used internally 
by Grist for such cases... which is undocumented, as far as we know.)

Output converters are easier: they receive the value retrieved by the API, and 
convert it to whatever you want - since it is your own code that consumes 
the value from now on, Grist is no longer involved and you can choose freely. 
Only you have to be prepared to accept input values of different types, since a 
GUI user will have more freedom in entering data anyway. 

Register a converter.
---------------------

Once you have written your converter functions, they have to be registered so 
that Pygrister learns about them and can use them.

An instance of the ``pygrister.api.GristApi`` class keeps an internal register 
of the converters to be applied. The register is just a dictionary - there is 
one ``in_converter`` for input converters, and one ``out_converter`` for output 
converters. 

Register dictionaries are nested, mapped by table names and column names, like 
this::

    from pygrister.api import GristApi
    grist = GristApi()
    gtist.in_converter = {
        'table_1': {'columnA': myconverter, 
                    'columnB': another_converter},
        'table_2': {'col_a': fancy_converter},
                         }

where ``myconverter`` etc. are, of course, the names of your previously 
defined converter functions. 

You are not required to register converters for every table in your database, 
or for every column in your table. If Pygrister doesn't find a converter for 
a specific column, it will simply pass the values as they are. Of course, 
you may register the same converter for more that one column.

Converters may also be passed at creation time::

    in_conv = {...}
    out_conv = {...}
    grist = GristApi(in_converter=in_conv, out_converter=out_conv)

You may add or remove converters at runtime, by simply manipulating the 
register dictionaries::

    grist.in_converter['table_1']['columnB'] = new_converter # change converter
    grist.in_converter.pop(['table_1']['columnA'])  # delete converter

To delete all converters, set the register to an empty dictionary::

    grist.in_converter = {} # reset input converters

See the test suite for more example of converter usage. 

Where converters are applied.
-----------------------------

Once registered, *input converters* are applied to the following APIs:

- ``GristApi.add_records``
- ``GristApi.update_records``
- ``GristApi.add_update_records``

*Output converters* are used with the following APIs:

- ``GristApi.list_records``
- ``GristApi.run_sql`` (special)
- ``GritsApi.run_sql_with_args`` (special)
  
To use converters with the two "sql" APIs, however, you will have to register 
them under the special ``sql`` key, as in

::

    grist.out_converter = {'sql': {'columnA': converter}}

This is because a sql query can pick data from any table, even multiple 
tables at the same time. If you want to run several different queries, you 
will have to register your different custom ``sql`` converters every time.

Finally, we remind you that currently the ``run_sql*`` Grist APIs are limited 
to ``SELECT`` statements only: there is no point in registering *input* 
converters for them. 

Handling conversion errors.
---------------------------

A converter, just like any Python function, may throw an exception. Pygrister 
handles this in a different way for input and output converters. 

At the moment, Pygrister does not intervene when an *input* converter fails, 
and simply let the resulting exception propagate (this may change in the 
future). 

An *output* converter, however, is handled a little more graciously. Should it 
fail with a ``ValueError`` or ``TypeError`` (the most common 
ones in such cases), then Pygrister will catch the exception and 
return either ``None`` (for null values) or ``str(value)`` (for anything 
else). Since ``str(x)`` always works in Python, this means that your 
output converter is almost always guaranteed to return "something" that 
you can work with - well, almost!, unless the converter fails with another, 
more exotic exception, that is. 

This is meant as a way of saving you from having to write all the boring 
``try/except`` (or ``if/else``) blocks in your converters, to account 
for the occasional null value or plain string that you may find in a Grist 
column. For instance, this is usually not necessary::

    def my_output_converter(value):
        if value is None:   # this is handled by Pygrister
            return None
        try:
            return some_fancy_data_conversion(value)
        except (TypeError, ValueError):  # also this
            returt str(value)

In many cases, this could be written just as ::

    def my_output_converter(value):
        # just do your actual conversion here
        return some_fancy_data_conversion(value)

Of course, if you don't like Pygrister's default behaviour, you can always 
catch the ``Value/TypeError`` yourself, and write your own handlers. 

As mentioned before, *input* converters, on the other hand, have no embedded 
exception handlers. The reasoning here is that the data to be written to 
the database should be entirely your responsibility, and Pygrister will 
simply refuse to guess. Therefore, you have to catch your own exceptions. 
The only guarantee is that the converters are applied immediately *before* 
passing the data to the API: if even one record triggers a failure in the 
converter, no data will be written to the database. 

A note on converting date/times.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A common use case for converters is adapting Grist timestamps in Date columns 
from/to complex Python types such as ``datetime.date``. If you are writing 
a converter like this, please note that Grist has a notion of "local time": 
Grist documents set a default timezone at the moment they are first created; 
date/time columns may set their own timezones (defaulting to the global document 
timezone); then the GUI widget may (or may not!) compensate for the users' local 
time offset when converting to database timestamps. See 
`the Grist documentation <https://support.getgrist.com/dates/#time-zones>`_ 
for details about this. 

The problem is, contrary to the GUI in the browser, the APIs have no way to know 
your local timezone: hence, if you insert a "naive" timestamp, without compensating 
for the timezone difference, chances are that you will end up with a different 
time value than you intended. A Pygrister converter can be the right place to 
address this, but you have to do it right. 

For instance, this won't work as expected::

    from datetime import datetime
    conv = {'mytable':
                {'datecol': lambda i: int(datetime.timestamp(i))}
            }
    grist = GristApi(in_converter=conv)
    the_date = datetime(2024, 8, 15)
    grist.add_records('mytable', [{'datecol': the_date}])

The problem here is that ``the_date`` is a "naive" date object, without 
timezone info. Grist will assume UTC+0, and further mangle the timestamp 
produced by the converter to compensate for the column's own timezone. 
Since your local time is probably different than UTC+0, when you'll check 
the inserted value with the GUI, you will see a different thing. 
(The test suite has examples of this behaviour.)

One *possible* solution is to use a timezone-aware Python object instead (see 
the module `zoneinfo <https://docs.python.org/3/library/zoneinfo.html>`_ for 
this)... however, you may also decide to set a different timezone for the 
Grist document, and/or columns, and/or use only UTC+0 dates... Timezone problems 
are `notoriously tricky <https://xkcd.com/1883/>`_ and there's no easy fix 
for that. Make sure to test extensively your converters!

