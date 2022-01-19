
import logging
import traceback
import sys
import jsonpickle
from rich.logging import RichHandler
import json
import os

FORMAT = "%(message)s"

# Get log level from env var LOGLEVEL
LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO').upper()

# Setup logger
rich_handler = RichHandler(omit_repeated_times=False)
logging.basicConfig(
    level=LOGLEVEL, format=FORMAT, datefmt="[%X]", handlers=[rich_handler]
)

# Wrapper for easy debug function
def wrap(log_f) :

    def f(*args, **kwargs) :
        args = list(args) + list("%s=%s" % (k, str(v)) for k,v in kwargs.items())
        msg = ", ".join(str(arg) for arg in args)
        log_f(msg)
    return f

# Export logger functions
logger = logging.getLogger("rich")
debug = wrap(logger.debug)
info = logger.info
warning = logger.warning
error = logger.error

# Uncaught exception hook
def log_except_hook(*exc_info):
    text = "".join(traceback.format_exception(*exc_info))
    logging.critical("Unhandled exception: %s", text)
    #logging.exception(exc_info)

sys.excepthook = log_except_hook


def obj2json(obj) :
    serialized = jsonpickle.encode(obj)
    return json.dumps(json.loads(serialized), indent=2)