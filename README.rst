pytivometa
==========

pytivometa is a script to create the metadata that pytivo (http://pytivo.org/,
https://github.com/wmcbrine/pytivo) can use when serving media files from a
computer to a TiVo.  It fetches metadata from Tivo's central servers,
https://www.thetvdb.com/ , and http://www.imdb.com to create text files and
put them in the proper place (near the associated video files) for pytivo to
find them.

Installation
------------

pytivometa requires Python 3.  Make sure Python 3 is installed on your system.

Install `pipx <https://github.com/pipxproject/pipx>`_ on your system, possibly with::

    pip install pipx

Then use pipx to install pytivometa and automatically put it in your binary
path::

    pipx install git+https://github.com/itsayellow/pytivometa

Running
-------

To run, execute ``pytivometa`` from the command line.

Use ``pytivometa --help`` for help.

Thanks
------

Based on the original pytivometathis by Graham Dunn and later Josh Harding
(https://sourceforge.net/projects/pytivometathis/).  This version has been
ported to python3 and extensively modified.
