
import logging
import traceback
import sys
import jsonpickle
from rich.logging import RichHandler
import json

FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
)  # set level=20 or logging.INFO to turn of debug

logger = logging.getLogger("rich")
debug = logger.debug
info = logger.info
warning = logger.warning
error = logger.error

# Setup logging
logging.basicConfig(format='%(message)s', level=logging.DEBUG)

# Uncaught exception hook
def log_except_hook(*exc_info):
    text = "".join(traceback.format_exception(*exc_info))
    logging.critical("Unhandled exception: %s", text)
    #logging.exception(exc_info)

sys.excepthook = log_except_hook

def obj2json(obj) :
    serialized = jsonpickle.encode(obj)
    return json.dumps(json.loads(serialized), indent=2)