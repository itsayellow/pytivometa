#!/usr/bin/env python3

import os.path
import textwrap

# debug level for messages of entire file
DEBUG_LEVEL = 0


def debug(level, text):
    if level <= DEBUG_LEVEL:
        print(text)


def ask_user(options_text, option_returns, max_options=5):
    indent = " "*4

    # Get number of movies found
    num_choices = len(option_returns)

    debug(2, "Found " + str(num_choices) + " matches.")
    # Show max max_options titles
    num_choices = min(num_choices, max_options)

    for i in range(num_choices):
        option_text = ""
        option_text_lines = options_text[i].splitlines()
        for line in option_text_lines:
            option_text += textwrap.fill(
                    line,
                    width=75,
                    initial_indent=indent,
                    subsequent_indent=indent
                    ) + "\n"
        option_text = option_text.strip()
        if num_choices < 10:
            print("%d   %s"%(i, option_text))
        else:
            print("%2d  %s"%(i, option_text))
    print("")
    try:
        choice_num = input(
                "Please choose the correct option, or 's' to skip [0]: "
                )
    except KeyboardInterrupt:
        print("\nCaught interrupt, exiting.")
        sys.exit(1)

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
        print("Option %d chosen."%choice_num)
        returnval = option_returns[choice_num]
    else:
        print("No choice recorded, skipping...")
        returnval = None

    return returnval

def mkdir_if_needed(dirname):
    if not os.path.exists(dirname):
        # Don't use os.makedirs() because that would only matter if -p named a
        #   non-existant dir (which we don't want to create)
        os.mkdir(dirname, 0o755)
    elif not os.path.isdir(dirname):
        raise OSError(
                'Can\'t create "' + dirname + '" as a dir, a file already ' +\
                        'exists with that name.'
                )
