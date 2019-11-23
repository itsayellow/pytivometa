#!/usr/bin/env python3

# ------------------------------------------------------------------------------
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
# ------------------------------------------------------------------------------
#    pytivometa - fetches metadata for video files for pytivo
#    Copyright (c) 2008, Graham Dunn <gmd@kurai.org>
#    Copyright (c) 2009-2011, Josh Harding <theamigo@gmail.com>
#    Copyright (C) 2017 Matthew A. Clapp
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
# ------------------------------------------------------------------------------

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
import getpass
import logging
import os
import os.path
import re
import stat
import sys

import pytivometa.movie_data
import pytivometa.rpc_search
import pytivometa.tv_data


# location of config dir and file for pytivometa
if sys.platform == "win32":
    CONFIG_DIR = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~/AppData/Local")),
        "pytivometa",
    )
else:
    CONFIG_DIR = os.path.expanduser("~/.config/pytivometa")
CONFIG_FILE_PATH = CONFIG_DIR + "/config"
LOG_FILE_PATH = CONFIG_DIR + "/log.txt"
NUM_LOGFILE_HIST = 5

# When using a subdir for metadata files, what should it be called
META_DIR = ".meta"

# Types of files we want to get metadata for
VIDEO_FILE_EXTS = [
    ".mpg",
    ".avi",
    ".ogm",
    ".mkv",
    ".mp4",
    ".mov",
    ".wmv",
    ".vob",
    ".m4v",
    ".flv",
]

# root logger
LOGGER = logging.getLogger(__name__)
LOGGED_MODULES = [__name__, "movie_data", "tv_data", "rpc_search", "tvdb_api_v2"]


def logging_setup(debug_level=False):
    """Setup logging for this and all submodules

    Args:
        debug_level (bool): whether to include DEBUG messages
    """
    # make sure config dir exists
    logdir_filepath = os.path.realpath(os.path.expanduser(CONFIG_DIR))
    os.makedirs(logdir_filepath, exist_ok=True)
    logfile_path = os.path.realpath(os.path.expanduser(LOG_FILE_PATH))
    # rename all old log files
    #   (log.txt.2 -> log.txt.3, log.txt.1 -> log.txt.2, log.txt -> log.txt.1
    for i in range(NUM_LOGFILE_HIST - 1, -1, -1):
        fname = logfile_path + ".%d" % i if i != 0 else logfile_path
        fname_plus_1 = logfile_path + ".%d" % (i + 1)
        if os.path.exists(fname):
            os.replace(fname, fname_plus_1)

    # create file log handler and set level to debug
    f_handler = logging.FileHandler(logfile_path)
    f_handler.setLevel(logging.DEBUG)
    # create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    # add formatter to f_handler
    f_handler.setFormatter(formatter)

    ## create console handler and set level to debug
    # c_handler = logging.StreamHandler()
    # c_handler.setLevel(logging.DEBUG)
    ## create formatter
    # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ## add formatter to c_handler
    # c_handler.setFormatter(formatter)

    # set global log level to either INFO or DEBUG depending on config
    if debug_level:
        global_log_level = logging.DEBUG
    else:
        global_log_level = logging.INFO

    # config all loggers
    for logger_name in LOGGED_MODULES:
        logging.getLogger(logger_name).setLevel(global_log_level)
        # logging.getLogger(logger_name).addHandler(c_handler)
        logging.getLogger(logger_name).addHandler(f_handler)

    # used to config root logger, but imdbpy module then spews to stdout :(
    # logging.getLogger().setLevel(global_log_level)
    # logging.getLogger().addHandler(f_handler)

    log_eff_level = LOGGER.getEffectiveLevel()
    LOGGER.log(
        log_eff_level, "Global log level set to %s", logging.getLevelName(log_eff_level)
    )


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

    LOGGER.debug("2,video_files after cull: %s", str(video_files))

    return video_files


def tvinfo_from_filename(filename):
    # Regexes for filenames that match TV shows.
    #   group 1: series search string (i.e. series name)
    # ?P<name> at the beginning of a group calls the group 'name'
    tv_res = [
        r"(.+)[Ss](?P<season>\d\d?)[Ee](?P<episode>\d+)",
        r"(.+?)(?: -)? ?(?P<season>\d+)[Xx](?P<episode>\d+)",
        r"(.*).(?P<year>\d\d\d\d).(?P<month>\d+).(?P<day>\d+).*",
        r"(.*).(?P<month>\d+).(?P<day>\d+).(?P<year>\d\d\d\d).*",
        r"(?i)(.+)(?P<season>\d?\d)(?P<episode>\d\d).*sitv",  # (?i) == re.I
    ]

    for tv_re in tv_res:
        match = re.search(tv_re, filename)
        if match:
            # Looks like a TV show
            break

    tv_info = {}
    if match:
        # fill in tv_info if we matched this filename to a regex
        tv_info["series"] = re.sub(r"[._]", " ", match.group(1)).strip()
        if match.lastindex >= 4:
            # str(int()) strips out leading zeroes
            tv_info["year"] = str(int(match.group("year")))
            tv_info["month"] = str(int(match.group("month")))
            tv_info["day"] = str(int(match.group("day")))
        else:
            tv_info["season"] = str(int(match.group("season")))
            tv_info["episode"] = str(int(match.group("episode")))

        LOGGER.debug(
            "2,    Series: %s\n"
            "    Season: %s\n"
            "    Episode: %s\n"
            "    Year: %s\n"
            "    Month: %s\n"
            "    Day: %s",
            tv_info["series"],
            tv_info.get("season", ""),
            tv_info.get("episode", ""),
            tv_info.get("year", ""),
            tv_info.get("month", ""),
            tv_info.get("day", ""),
        )

    return tv_info


def check_interactive():
    if sys.platform not in ["win32", "cygwin"]:
        # On unix-like platforms, set interactive mode when running from a
        #   terminal
        if os.isatty(sys.stdin.fileno()):
            return True
    # On windows systems set interactive when running from a console
    elif "PROMPT" in list(os.environ.keys()):
        return True
    return False


def create_genre_dir(genre_dir):
    # Python doesn't support making symlinks on Windows.
    if sys.platform in ["win32", "cygwin"]:
        print(
            "The genre feature doesn't work on Windows as symlinks "
            "aren't well supported."
        )
        genre_dir = None
    else:
        if not os.path.exists(genre_dir):
            os.makedirs(genre_dir, 0o755)
        elif not os.path.isdir(genre_dir):
            raise OSError(
                "Can't create \""
                + genre_dir
                + '" as a dir, a '
                + "file already exists with that name."
            )
        else:
            print(
                "Note: If you've removed videos, there may be old "
                "symlinks in '" + genre_dir + "'.  If there's "
                "nothing else in there, you can just remove the "
                "whole thing first, then run this again (e.g. "
                "rm -rf '" + genre_dir + "'), but be careful."
            )
    return genre_dir


def process_dir(
    dir_proc, dir_files, tv_data_acc, movie_data_acc, use_metadir=False, clobber=False
):
    LOGGER.debug("\n## Looking for videos in: %s", dir_proc)

    video_files = get_video_files(dir_proc, dir_files)

    # See if we're in a "Trailer" folder.
    is_trailer = "trailer" in os.path.abspath(dir_proc).lower()

    # dir to put metadata in is either dir_proc or dir_proc/META_DIR
    if use_metadir or os.path.isdir(os.path.join(dir_proc, META_DIR)):
        meta_dir = os.path.join(dir_proc, META_DIR)
    else:
        meta_dir = dir_proc

    for filename in video_files:
        meta_filepath = os.path.join(meta_dir, filename + ".txt")

        LOGGER.debug("\n--->working on: %s", filename)
        LOGGER.debug("2,Metafile is: %s", meta_filepath)

        if os.path.exists(meta_filepath) and not clobber:
            LOGGER.debug("Metadata file already exists, skipping.")
        else:
            # get info in dict if filename looks like tv episode, {} otherwise
            tv_info = tvinfo_from_filename(filename)

            if tv_info:
                # assume tv if filename matches tv format
                tv_data_acc.parse_tv(tv_info, meta_filepath, dir_proc)
            else:
                # assume movie if filename not matching tv
                movie_data_acc.parse_movie(
                    dir_proc, filename, meta_filepath, is_trailer=is_trailer
                )


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
        description="Retrieve information from TVDB and IMDB to add "
        "TiVo metadatada to all media files in the current "
        "directory.  TV info from http://www.thetvdb.com/ ."
        "They welcome user contributions of show data.",
    )

    # optional positional list of directories:
    parser.add_argument(
        "dir",
        nargs="*",
        default=["."],
        help="Specific directory(-ies) to process. (Default is current directory.)",
    )

    # switches/options:
    parser.add_argument(
        "-c",
        "--createconfig",
        action="store_true",
        help="Create config file: "
        + CONFIG_FILE_PATH
        + " with default settings and immediately exit.",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="More detailed debugging messages are printed to log file.",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        dest="clobber",
        help="Force overwrite of existing metadata",
    )
    parser.add_argument(
        "-t",
        "--tidy",
        action="store_true",
        dest="metadir",
        help="Save metadata files in .meta subdirectory. ",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Generate metadata for all files in sub dirs too.",
    )
    parser.add_argument(
        "-g",
        "--genre",
        help="Specify a directory in which to place symlinks to shows, "
        "organized by genre.",
    )
    parser.add_argument(
        "-w",
        "--wait",
        dest="timeout",
        type=int,
        help="How many seconds to wait for a connection to thetvdb.com "
        "before giving up. (Default: 5s)",
    )

    args = parser.parse_args(argv)

    return args


def get_config_file():
    config_data = {}
    config_filepath = os.path.expanduser(CONFIG_FILE_PATH)
    if os.path.isfile(config_filepath):
        with open(config_filepath, "r") as config_fh:
            for line in config_fh:
                line = re.sub(r"#.*", "", line)
                line = line.lstrip()
                line = line.rstrip("\n\r")
                if "=" in line:
                    (key, value) = line.split("=", maxsplit=1)
                    key = key.strip()
                    config_data[key] = value

    # convert 'true' or 'True' to True, else False
    if "metadir" in config_data:
        config_data["metadir"] = "true" in config_data["metadir"].lower()
    if "recursive" in config_data:
        config_data["recursive"] = "true" in config_data["recursive"].lower()
    if "clobber" in config_data:
        config_data["clobber"] = "true" in config_data["clobber"].lower()

    # convert str number to int
    if "timeout" in config_data:
        config_data["timeout"] = int(config_data["timeout"])
    if "debug" in config_data:
        config_data["debug"] = "true" in config_data["debug"].lower()

    return config_data


def default_config_values():
    """Master location of all default config values
    """
    config_data = {
        "clobber": False,
        "createconfig": False,
        "debug": False,
        "genre": None,
        "metadir": False,
        "recursive": False,
        "timeout": 5,
        "country": "USA",
        "language": "English",
    }
    return config_data


def create_config_file():
    def_config = default_config_values()
    config_default_lines = [
        "# pytivometa config file",
        "# Command-line options will override these options.",
        "\n# for RPC searches.  Omit or leave blank to disable.",
        "# If username is present and password is blank, user will be",
        "#     asked for password upon every execution of program.",
        "username=",
        "password=",
        "\n# When searching for matching entries, prefer descriptions",
        "#     in 'language' and info matching 'country'",
        "language=%s" % def_config["language"],
        "country=%s" % def_config["country"],
        "\n# Save metadata files in .meta subdirectory: True or False",
        "metadir=%s" % def_config["metadir"],
        "\n# How many seconds to wait for a connection to thetvdb.com",
        "timeout=%d" % def_config["timeout"],
        "\n# Generate metadata for all files in sub dirs too: True or False",
        "recursive=%s" % def_config["recursive"],
        "\n# Specify a directory in which to place symlinks to shows, ",
        "#    organized by genre.  Leave blank to disable.",
        "genre=",
        "\n# Force overwrite of existing metadata: True or False",
        "clobber=%s" % def_config["clobber"],
        "\n# Extra debug messages in log file: True or False",
        "debug=%s" % def_config["debug"],
    ]
    config_filepath = os.path.realpath(os.path.expanduser(CONFIG_FILE_PATH))

    print("Creating default config file: " + CONFIG_FILE_PATH)
    if os.path.isfile(config_filepath):
        print(CONFIG_FILE_PATH)
        print("    Config file exists.  Not writing default config file.")
        return
    try:
        os.makedirs(os.path.dirname(config_filepath), exist_ok=True)
    except OSError:
        print(
            "Couldn't make config file, error creating directory: "
            + os.path.dirname(CONFIG_FILE_PATH)
        )
        return
    try:
        with open(config_filepath, "w") as config_fh:
            for line in config_default_lines:
                print(line, file=config_fh)
    except:
        # TODO: find specific error, replace raise with return
        print("Couldn't make config file: " + CONFIG_FILE_PATH)
        LOGGER.error("Error writing config file", exc_info=True)
        raise
    os.chmod(config_filepath, stat.S_IRUSR + stat.S_IWUSR)


def get_rpc(username=None, password=None):
    # get RPC username and password if it exists
    if username is not None and not password:
        password = getpass.getpass("tivo.com password: ")

    if username and password:
        try:
            rpc_remote = pytivometa.rpc_search.Remote(username, password)
        except pytivometa.rpc_search.AuthError:
            print(
                "Bad password or username for RPC."
                "    Unable to use RPC search capability"
            )
            LOGGER.debug("No rpc_remote")
            rpc_remote = None
    else:
        rpc_remote = None

    if rpc_remote is not None:
        print("Successful login to RPC.  RPC info enabled.")

    return rpc_remote


def main(argv):
    # start with config default values
    config = default_config_values()

    # get config from config file if present
    config.update(get_config_file())

    # command-line arguments (overrides config file)
    config.update(vars(process_command_line(argv)))

    # Set up logging
    logging_setup(config["debug"])

    # create default config file in proper place if requested, and immediately
    #   exit
    if config["createconfig"]:
        create_config_file()
        return 0

    # set interactive if we are in an interactive shell
    interactive = check_interactive()

    # create/set genre dir if specified and possible
    if config["genre"]:
        genre_dir = create_genre_dir(config["genre"])
    else:
        genre_dir = None

    # get rpc_remote if possible
    rpc_remote = get_rpc(
        username=config.get("username", None), password=config.get("password", None)
    )

    # Initalize tv_data access
    tv_data_acc = pytivometa.tv_data.TvData(
        interactive=interactive, clobber=config["clobber"], rpc_remote=rpc_remote
    )
    # Initalize movie_data access
    movie_data_acc = pytivometa.movie_data.MovieData(
        interactive=interactive,
        genre_dir=genre_dir,
        country=config["country"],
        lang=config["language"],
        rpc_remote=rpc_remote,
    )

    # process all dirs
    for search_dir in config["dir"]:
        if config["recursive"]:
            for (dirpath, _, dir_files) in os.walk(search_dir):
                dirname = os.path.basename(dirpath)
                # only non-hidden dirs (no dirs starting with .)
                #   but '.' dir is OK
                if not re.search(r"\..+", dirname):
                    process_dir(
                        dirpath,
                        dir_files,
                        tv_data_acc,
                        movie_data_acc,
                        use_metadir=config["metadir"],
                        clobber=config["clobber"],
                    )
        else:
            dir_files = os.listdir(search_dir)
            process_dir(
                search_dir,
                dir_files,
                tv_data_acc,
                movie_data_acc,
                use_metadir=config["metadir"],
                clobber=config["clobber"],
            )

    # exit status 0 if everything's ok
    return 0


def cli_start():
    try:
        status = main(sys.argv)
    except KeyboardInterrupt:
        print("\nStopped by Keyboard Interrupt", file=sys.stderr)
        # exit error code for Ctrl-C
        status = 130
    except Exception:
        # make sure any uncaught errors end up in log
        LOGGER.error("Uncaught error: ", exc_info=True)
        raise

    return status


if __name__ == "__main__":
    sys.exit(cli_start())
