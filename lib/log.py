
import logging
import traceback
import sys

from typing import List

import jsonpickle
import json
import os
import threading

# Get log level from env var LOGLEVEL
from rich.console import Console
from rich.logging import RichHandler
from six import raise_from

LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO').upper()

# Global var holding context data
log_context_data = threading.local()

class ThreadingLocalContextFilter(logging.Filter):
    """
    This is a filter which injects contextual information from `threading.local` (log_context_data) into the log.
    """
    def __init__(self, attributes: List[str]):
        super().__init__()
        self.attributes = attributes

    def filter(self, record):
        record.context = ":".join(getattr(log_context_data, a, '-') for a in self.attributes)
        return True

# Wrapper for easy debug function
def wrap(log_f) :
    def f(*args, **kwargs) :
        args = list(args) + list("%s=%s" % (k, str(v)) for k,v in kwargs.items())
        msg = ", ".join(str(arg) for arg in args)
        log_f(msg)
    return f

# Uncaught exception hook
def log_except_hook(*exc_info):
    trace = "".join(traceback.format_exception(*exc_info))
    logger.critical("Unhandled exception. %s", trace)


def obj2json(obj) :
    serialized = jsonpickle.encode(obj)
    return json.dumps(json.loads(serialized), indent=2)

class LogContext(object):
    def __init__(self, **context):
        self.context: dict = context

    def __enter__(self):
        for key, val in self.context.items():
            setattr(log_context_data, key, val)
        return self

    def __exit__(self, et, ev, tb):
        for key in self.context.keys():
            delattr(log_context_data, key)

        if ev != None :
            raise_from(Exception(
                "Exception: %s. Context : %s" % (str(ev), str(self.context))), ev)
            return True



# Setup logger
if not sys.stdout.isatty():
    console = Console(
        file=sys.stderr,
        force_terminal=False,
        width=140)
else :
    console = None

rich_handler = RichHandler(omit_repeated_times=False, console=console)
rich_handler.addFilter(ThreadingLocalContextFilter(["network", "station_id", "file"]))
logging.basicConfig(
    level=LOGLEVEL,
    format="{context}\t{message}",
    style="{",
    datefmt="[%X]",
    handlers=[rich_handler])

# Export logger functions
logger = logging.getLogger("rich")
debug = wrap(logger.debug)
info = logger.info
warning = logger.warning
error = logger.error
critical = logger.critical

sys.excepthook = log_except_hook

