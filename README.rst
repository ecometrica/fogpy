#####
FogPy
#####

FogPy is a python interface to FogBugz' API.

For now it doesn't contain much. The FogBuzAPI class allows you to login 
and run any command through the API, returning XML.

The TimeReporting class (which really was the whole point of making this
in the first place, but fogpy should be extended more generically) lets you
generate CSV reports of hours spent per tag per developer. That way, you 
can tag bugs with things like "ClientA" or "R&D", and generate that report
to figure out how much to bill to ClientA, or how much to capitalize as
R&D and claim as credits.

Please feel free to add to it. My own idea for improvements was to make
classes for Bug and Person, which would let you easily search and access 
them. For example, Bug[123] would return a Bug object with id 123, 
fetching it from fogbugz if it hasn't been fetched yet. All the bug
fields would be attributes on the Bug object. Perhaps a base set of 
attributes would be fetched initially, and others would be fetched 
on-demand - see TimeReporting.{devs,bugs} for examples of on-demand 
fetching.

Time Reporting
==============

Example usage::
    
    ./fogpy/timereport.py -u YOURFBUSERNAME -p YOURFBPASS -o /tmp/foo.csv  2011-08-31T00:00:00Z 2011-09-30T00:00:00Z

