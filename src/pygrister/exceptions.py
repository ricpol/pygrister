"""
Pygrister exception hierarchy. 
------------------------------

Exceptions listed here can be raised by Pygrister, and they concern 
its internal functioning. Note that Grist API calls themselves, however, 
are delegated to Requests, and will (much more frequently!) throw 
the exceptions provided by Requests.
"""

class GristApiException(Exception): 
    """The base GristApi exception."""
    pass

class GristApiNotConfigured(GristApiException): 
    """A configuration error occurred."""
    pass

class GristApiNotImplemented(GristApiException): 
    "This API is not yet implemented by Pygrister."""
    pass

class GristApiInSafeMode(GristApiException): 
    """Pygrister is in safe mode, no writing to the db is possible."""
    pass
