#!/usr/bin/env python3

#    tvdb_api_v2.py - module to access tvdb data using tvdb api v2
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

import logging
import os.path
import textwrap


# Set up logger
LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


def ask_user(options_text, option_returns, max_options=5):
    indent = " " * 4

    # Get number of movies found
    num_choices = len(option_returns)

    LOGGER.debug("2,Found %d matches.", num_choices)
    # Show max max_options titles
    num_choices = min(num_choices, max_options)

    for i in range(num_choices):
        option_text = ""
        option_text_lines = options_text[i].splitlines()
        for line in option_text_lines:
            option_text += (
                textwrap.fill(
                    line, width=75, initial_indent=indent, subsequent_indent=indent
                )
                + "\n"
            )
        option_text = option_text.strip()
        if num_choices < 10:
            print("%d   %s" % (i, option_text))
        else:
            print("%2d  %s" % (i, option_text))
    print("")
    choice_num = input("Please choose the correct option, or 's' to skip [0]: ")

    if not choice_num:
        # Empty string, default to the top choice
        choice_num = 0
    else:
        # Check for non-numeric input
        try:
            choice_num = int(choice_num)
        except ValueError:
            choice_num = None
        else:
            # Check for out-of-range input
            if choice_num < 0 or choice_num > num_choices:
                choice_num = None

    if choice_num is not None:
        print("Option %d chosen." % choice_num)
        returnval = option_returns[choice_num]
    else:
        print("No choice recorded, skipping...")
        returnval = None

    return returnval


def mkdir_if_needed(dirname):
    # Don't use os.makedirs() because that would only matter if -p named a
    #   non-existant dir (which we don't want to create)
    if not os.path.exists(dirname):
        os.mkdir(dirname, 0o755)
    elif not os.path.isdir(dirname):
        raise OSError(
            "Can't create \""
            + dirname
            + '" as a dir, a file already '
            + "exists with that name."
        )
