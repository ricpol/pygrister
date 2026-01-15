GRY - The Grist Cli Tool
========================

Gry is a command line tool to interact with the Grist Apis. 

Gry is written in Python, and leverages on the Pygrister library to wrap 
the Grist Apis. This hardly matters to you, though: this bundle of Gry 
is completely standalone, meaning that you don't need Python and 
Pygrister on your computer.
At the moment, the Gry bundle is available only for Windows. 
Mac/Linux users will have to install Pygrister (ie., "pip install pygrister"): 
Gry is already included with the Pygrister library.


How to use the Gry standalone bundle
------------------------------------

Get the compressed distribution on GitHub, unzip it into a folder. Open 
your system shell, navigate to the directory where you extracted the 
bundle, and type "gry" to the command prompt. 

(Please note: Gry is a *command line* tool, so no grapich interface is 
available. On Windows, if you double click on the "gry.exe" icon, the 
command prompt will flash briefly on screen, then immediately close itself.)

Gry needs to know your API key and a few other things, in order to work. 
You will find a stub "gryconfig.json" file in the same top directory as 
the Gry executable. Open it, fill in the missing information, and you are 
ready to go. 
(Advanced users may also want to edit "gryrequest.json" to pass additional 
information to the underlying Requests library: if you don't know what 
this means, it's fine - just ignore this file.)


Useful links
------------

Get the standalone version of the Gry tool here:
https://github.com/ricpol/pygrister/releases (it's the "gry.zip" file)

Learn about Gry:
https://pygrister.readthedocs.io/en/latest/gry.html

Learn about the Grist Apis:
https://support.getgrist.com/rest-api/ (intro)
https://support.getgrist.com/api/ (reference)


License
-------

Gry and Pygrister are (c) Riccardo Polignieri 
Gry is released under the MIT license: see
https://github.com/ricpol/pygrister/blob/main/LICENSE.txt
