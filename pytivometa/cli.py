#!/usr/bin/env python3

import sys

import pytivometa.pytivometa


def pytivometa():
    try:
        status = pytivometa.pytivometa.main(sys.argv)
    except KeyboardInterrupt:
        print("\nStopped by Keyboard Interrupt", file=sys.stderr)
        # exit error code for Ctrl-C
        status = 130
    except Exception as error:
        # make sure any uncaught errors end up in log
        LOGGER.error("Uncaught error: ", exc_info=True)
        raise

    return status
