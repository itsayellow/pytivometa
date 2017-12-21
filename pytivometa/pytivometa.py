#!/usr/bin/env python3
# Copyright (c) 2008, Graham Dunn <gmd@kurai.org>
# Copyright (c) 2009-2011, Josh Harding <theamigo@gmail.com>
# Copyright (c) 2017, Matthew Clapp <itsayellow+dev@gmail.com>
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
#   modification, are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#       this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#    * Neither the name of the author nor the names of the contributors may be
#       used to endorse or promote products derived from this software without
#       specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# Version : 0.5

# Python required: > 3.0

"""Look in current directory, or specified directory, find all video files,
fetch their metadata, and write metadata out into format that pytivo can
parse and use.

If the file name of a movie has a year in parentheses
(e.g. "Old Movie (1934)"), then it will aid in the search for the proper movie.
    Wild Strawberries (1957).m4v

A filename will be considered a TV show if it has part of it with something
like a season and episode specification as part of it.  (e.g. "S01E02",
or "s01e02", etc.)  Also, an air-date will allow an episode to be found.
    Friends.s02e03.m4v
    friends.2004.4.29.m4v
"""

import argparse
import os
import os.path
import re
import stat
import sys
import textwrap


import movie_data
import tv_data
import tvdb_api_v2


# location of config file for pytivometa
CONFIG_FILE_PATH = "~/.config/pytivometa/config"

# When using a subdir for metadata files, what should it be called
META_DIR = '.meta'

# Types of files we want to get metadata for
VIDEO_FILE_EXTS = [
        ".mpg", ".avi", ".ogm", ".mkv", ".mp4",
        ".mov", ".wmv", ".vob", ".m4v", ".flv"
        ]

# string encoding for output to metadata files.  Tivo is UTF8 compatible so use
#   that for file output
FILE_ENCODING = 'UTF-8'

# debug level for messages of entire file
DEBUG_LEVEL = 0


def debug(level, text):
    if level <= DEBUG_LEVEL:
        print(text)


def get_video_files(dirname, dir_files):
    """Get list of file info objects for files of particular extensions, and
    subdirectories for recursive search
    """
    # get list of video files
    video_files = []
    for dir_file in dir_files:
        full_path = os.path.join(dirname, dir_file)
        (entry_base, entry_ext) = os.path.splitext(dir_file)
        if entry_ext in VIDEO_FILE_EXTS and entry_base and os.path.isfile(full_path):
            video_files.append(dir_file)
    video_files.sort()

    debug(2, "video_files after cull: %s" % str(video_files))

    return video_files

def tvinfo_from_filename(filename):
    # Regexes for filenames that match TV shows.
    #   group 1: series search string (i.e. series name)
    # ?P<name> at the beginning of a group calls the group 'name'
    tv_res = [
            r'(.+)[Ss](?P<season>\d\d?)[Ee](?P<episode>\d+)',
            r'(.+?)(?: -)? ?(?P<season>\d+)[Xx](?P<episode>\d+)',
            r'(.*).(?P<year>\d\d\d\d).(?P<month>\d+).(?P<day>\d+).*',
            r'(.*).(?P<month>\d+).(?P<day>\d+).(?P<year>\d\d\d\d).*',
            r'(?i)(.+)(?P<season>\d?\d)(?P<episode>\d\d).*sitv' # (?i) == re.I
            ]

    for tv_re in tv_res:
        match = re.search(tv_re, filename)
        if match:
            # Looks like a TV show
            break

    tv_info = {}
    if match:
        # fill in tv_info if we matched this filename to a regex
        tv_info['series'] = re.sub(r'[._]', ' ', match.group(1)).strip()
        if match.lastindex >= 4:
            # str(int()) strips out leading zeroes
            tv_info['year'] = str(int(match.group('year')))
            tv_info['month'] = str(int(match.group('month')))
            tv_info['day'] = str(int(match.group('day')))
        else:
            tv_info['season'] = str(int(match.group('season')))
            tv_info['episode'] = str(int(match.group('episode')))

        debug(2, "    Series: %s\n"%tv_info['series'] + \
                "    Season: %s\n"%tv_info.get('season', '') + \
                "    Episode: %s\n"%tv_info.get('episode', '') + \
                "    Year: %s\n"%tv_info.get('year', '') + \
                "    Month: %s\n"%tv_info.get('month', '') + \
                "    Day: %s"%tv_info.get('day', '')
                )

    return tv_info

def process_dir(dir_proc, dir_files, tvdb_token, interactive=False,
        use_metadir=False, clobber=False, genre_dir=None):
    debug(1, "\n## Looking for videos in: " + dir_proc)

    video_files = get_video_files(dir_proc, dir_files)

    # See if we're in a "Trailer" folder.
    is_trailer = 'trailer' in os.path.abspath(dir_proc).lower()

    # dir to put metadata in is either dir_proc or dir_proc/META_DIR
    if use_metadir or os.path.isdir(os.path.join(dir_proc, META_DIR)):
        meta_dir = os.path.join(dir_proc, META_DIR)
    else:
        meta_dir = dir_proc

    for filename in video_files:
        meta_filepath = os.path.join(meta_dir, filename + '.txt')

        debug(1, "\n--->working on: %s" % filename)
        debug(2, "Metafile is: " + meta_filepath)

        if os.path.exists(meta_filepath) and not clobber:
            debug(1, "Metadata file already exists, skipping.")
        else:
            # get info in dict if filename looks like tv episode, {} otherwise
            tv_info = tvinfo_from_filename(filename)

            if tv_info:
                # assume tv if filename matches tv format
                tv_data.parse_tv(tvdb_token, tv_info, meta_filepath, dir_proc,
                        interactive=interactive, clobber=clobber
                        )
            else:
                # assume movie if filename not matching tv
                movie_data.parse_movie(dir_proc, filename, meta_filepath,
                        interactive=interactive, is_trailer=is_trailer,
                        genre_dir=genre_dir
                        )

def check_interactive():
    if sys.platform not in ['win32', 'cygwin']:
        # On unix-like platforms, set interactive mode when running from a
        #   terminal
        if os.isatty(sys.stdin.fileno()):
            return True
    # On windows systems set interactive when running from a console
    elif 'PROMPT' in list(os.environ.keys()):
        return True
    return False

def create_genre_dir(genre_dir):
    # Python doesn't support making symlinks on Windows.
    if sys.platform in ['win32', 'cygwin']:
        debug(0, "The genre feature doesn't work on Windows as symlinks " +\
                "aren't well supported."
                )
        genre_dir = None
    else:
        if not os.path.exists(genre_dir):
            os.makedirs(genre_dir, 0o755)
        elif not os.path.isdir(genre_dir):
            raise OSError(
                    'Can\'t create "' + genre_dir + '" as a dir, a ' + \
                            'file already exists with that name.'
                    )
        else:
            debug(0, "Note: If you've removed videos, there may be old " +\
                    "symlinks in '" + genre_dir + "'.  If there's " +\
                    "nothing else in there, you can just remove the " +\
                    "whole thing first, then run this again (e.g. " +\
                    "rm -rf '" + genre_dir + "'), but be careful."
                    )
    return genre_dir

def process_command_line(argv):
    """Process command line invocation arguments and switches.

    Args:
        argv: list of arguments, or `None` from ``sys.argv[1:]``.

    Returns:
        args: Namespace with named attributes of arguments and switches
    """
    argv = argv[1:]

    # initialize the parser object
    #   argument_default=SUPPRESS means do not add option to namespace
    #       if it is not present (we use separate defaults fxn)
    parser = argparse.ArgumentParser(
            argument_default=argparse.SUPPRESS,
            description="Retrieve information from TVDB and IMDB to add "\
                    "TiVo metadatada to all media files in the current "\
                    "directory.  TV info from http://www.thetvdb.com/ ."\
                    "They welcome user contributions of show data."
                    )

    # optional positional list of directories:
    parser.add_argument(
            "dir", nargs="*", default=['.'],
            help="Specific directory(-ies) to process. (Default is current "\
                    "directory.)"
            )

    # switches/options:
    parser.add_argument(
            "-c", "--createconfig", action="store_true", default=False,
            help="Create default config file: " + CONFIG_FILE_PATH
            )
    parser.add_argument(
            "-d", "--debug", action="count",
            help="Turn on debugging. More -d's increase debug level."
            )
    parser.add_argument(
            "-f", "--force", action="store_true", dest="clobber",
            help="Force overwrite of existing metadata"
            )
    parser.add_argument(
            "-t", "--tidy", action="store_true", dest="metadir",
            help="Save metadata files in .meta subdirectory. "
            )
    parser.add_argument(
            "-r", "--recursive", action="store_true",
            help="Generate metadata for all files in sub dirs too."
            )
    parser.add_argument(
            "-g", "--genre",
            help="Specify a directory in which to place symlinks to shows, "\
                    "organized by genre."
            )
    parser.add_argument(
            "-w", "--wait", dest="timeout", type=int,
            help="How many seconds to wait for a connection to thetvdb.com "\
                    "before giving up. (Default: 5s)"
            )

    args = parser.parse_args(argv)

    return args

def get_config_file():
    config_data = {}
    config_filepath = os.path.expanduser(CONFIG_FILE_PATH)
    if os.path.isfile(config_filepath):
        with open(config_filepath, 'r') as config_fh:
            for line in config_fh:
                line = re.sub(r'^(\s*#.*)', '', line)
                data_re = re.search(r'^(\S+)=(\S.*)$', line)
                if data_re:
                    config_data[data_re.group(1)] = data_re.group(2)

    # convert 'true' or 'True' to True, else False
    if 'metadir' in config_data:
        config_data['metadir'] = 'true' in config_data['metadir'].lower()
    if 'recursive' in config_data:
        config_data['recursive'] = 'true' in config_data['recursive'].lower()
    if 'clobber' in config_data:
        config_data['clobber'] = 'true' in config_data['clobber'].lower()

    # convert str number to int
    if 'timeout' in config_data:
        config_data['timeout'] = int(config_data['timeout'])
    if 'debug' in config_data:
        config_data['debug'] = int(config_data['debug'])

    return config_data

def default_config_values():
    """Master location of all default config values
    """
    config_data = {
            'clobber': False,
            'createconfig': False,
            'debug': 0,
            'genre': None,
            'metadir': False,
            'recursive': False,
            'timeout': 5,
            }
    return config_data

def create_config_file():
    def_config = default_config_values()
    config_default_lines = [
            "# pytivometa config file",
            "# Command-line options will override these options.",
            "\n# for RPC searches.  Leave blank to disable.",
            "username=",
            "password=",
            "\n# How many seconds to wait for a connection to thetvdb.com",
            "timeout=%d"%def_config['timeout'],
            "\n# Save metadata files in .meta subdirectory if true.",
            "metadir=%s"%def_config['metadir'],
            "\n# Generate metadata for all files in sub dirs too if true.",
            "recursive=%s"%def_config['recursive'],
            "\n# Specify a directory in which to place symlinks to shows, ",
            "#    organized by genre.  Leave blank to disable.",
            "genre=",
            "\n# Force overwrite of existing metadata if true.",
            "clobber=%s"%def_config['clobber'],
            "\n# Debug level: 0=no debug messages, 1=some, 2=more, 3=most.",
            "debug=%d"%def_config['debug'],
            ]
    config_filepath = os.path.expanduser(CONFIG_FILE_PATH)

    print("Creating default config file: " + CONFIG_FILE_PATH)
    if os.path.isfile(config_filepath):
        print("Config file exists.  Not default config file: " + CONFIG_FILE_PATH)
        return
    try:
        os.makedirs(os.path.dirname(config_filepath), exist_ok=True)
    except OSError:
        print("Couldn't make config file, error creating directory: " +\
                os.path.dirname(CONFIG_FILE_PATH))
        return
    try:
        with open(config_filepath, 'w') as config_fh:
            for line in config_default_lines:
                print(line, file=config_fh)
    except:
        # TODO: find specific error, replace raise with return
        print("Couldn't make config file: " + CONFIG_FILE_PATH)
        raise
    os.chmod(config_filepath, stat.S_IRUSR + stat.S_IWUSR)

def main(argv):
    global DEBUG_LEVEL

    # start with config default values
    config = default_config_values()

    # get config from config file if present
    config.update(get_config_file())

    # command-line arguments (overrides config file)
    config.update(vars(process_command_line(argv)))

    # create default config file in proper place if requested
    if config['createconfig']:
        create_config_file()

    # set master debug message level for all modules
    # TODO: such a hack
    DEBUG_LEVEL = config['debug']
    tvdb_api_v2.DEBUG_LEVEL = config['debug']
    tv_data.DEBUG_LEVEL = config['debug']
    tv_data.common.DEBUG_LEVEL = config['debug']
    movie_data.DEBUG_LEVEL = config['debug']
    movie_data.common.DEBUG_LEVEL = config['debug']

    # set interactive if we are in an interactive shell
    interactive = check_interactive()

    debug(2, "Metadata File Output encoding: %s\n" % FILE_ENCODING)

    # Initalize tvdb session token
    tvdb_token = tvdb_api_v2.get_session_token()

    # create/set genre dir if specified and possible
    if config['genre']:
        genre_dir = create_genre_dir(config['genre'])
    else:
        genre_dir = None

    # process all dirs
    for search_dir in config['dir']:
        if config['recursive']:
            for (dirpath, _, dir_files) in os.walk(search_dir):
                dirname = os.path.basename(dirpath)
                # only non-hidden dirs (no dirs starting with .)
                #   but '.' dir is OK
                if not re.search(r'\..+', dirname):
                    process_dir(dirpath, dir_files, tvdb_token,
                            interactive=interactive,
                            use_metadir=config['metadir'],
                            clobber=config['clobber'],
                            genre_dir=genre_dir
                            )
        else:
            dir_files = os.listdir(search_dir)
            process_dir(search_dir, dir_files, tvdb_token,
                    interactive=interactive,
                    use_metadir=config['metadir'],
                    clobber=config['clobber'],
                    genre_dir=genre_dir
                    )

    # exit status 0 if everything's ok
    return 0

if __name__ == "__main__":
    try:
        status = main(sys.argv)
    except KeyboardInterrupt:
        print("Stopped by Keyboard Interrupt", file=sys.stderr)
        # exit error code for Ctrl-C
        status = 130

    sys.exit(status)
