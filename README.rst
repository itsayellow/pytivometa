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

To install required modules for pytivometa to work, execute the following
command::

    pip3 install -r requirements.txt

On Windows, you may need to run pip3 from a command prompt in "run as
administrator" mode (right-click on the Command Prompt in the Start Menu and
select "Run as Administrator") to allow the installation of new python modules.

Running
-------

To run, execute ``pytivometa.py`` in the ``pytivometa`` directory from the
command line.  Be sure to keep all the files in the ``pytivometa`` directory
together in the same directory.

Thanks
------

Based on the original pytivometathis by Graham Dunn and later Josh Harding
(https://sourceforge.net/projects/pytivometathis/).  This version has been
ported to python3 and extensively modified.
