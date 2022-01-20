
import logging
import traceback
import sys
from datetime import datetime
from inspect import Traceback
from logging import LogRecord
from pathlib import Path
from typing import List, Optional

import jsonpickle
from rich.logging import RichHandler
import json
import os
import threading

# Get log level from env var LOGLEVEL
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
        for a in self.attributes:
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
    text = "".join(traceback.format_exception(*exc_info))
    logging.critical("Unhandled exception: %s", text)


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


class RichHandlerContext(RichHandler) :
    """Rich Handler using 'context' atttribute of record as file path """
    def render(
        self,
        *,
        record: LogRecord,
        traceback: Optional[Traceback],
        message_renderable: "ConsoleRenderable",
    ) -> "ConsoleRenderable":
        """Render log for display.

        Args:
            record (LogRecord): logging Record.
            traceback (Optional[Traceback]): Traceback instance or None for no Traceback.
            message_renderable (ConsoleRenderable): Renderable (typically Text) containing log message contents.

        Returns:
            ConsoleRenderable: Renderable to display log.
        """
        level = self.get_level_text(record)
        time_format = None if self.formatter is None else self.formatter.datefmt
        log_time = datetime.fromtimestamp(record.created)

        log_renderable = self._log_render(
            self.console,
            [message_renderable] if not traceback else [message_renderable, traceback],
            log_time=log_time,
            time_format=time_format,
            level=level,
            path=record.context,
            line_no=None,
            link_path=record.pathname if self.enable_link_path else None,
        )
        return log_renderable

# Setup logger
rich_handler = RichHandlerContext(omit_repeated_times=False)
rich_handler.addFilter(ThreadingLocalContextFilter(["network", "station_id", "file"]))
logging.basicConfig(
    level=LOGLEVEL,
    format="{message}",
    style="{",
    datefmt="[%X]",
    handlers=[rich_handler])

# Export logger functions
logger = logging.getLogger("rich")
debug = wrap(logger.debug)
info = logger.info
warning = logger.warning
error = logger.error

sys.excepthook = log_except_hook

