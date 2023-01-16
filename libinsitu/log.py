
import logging
import traceback
import sys
from inspect import Traceback
from logging import LogRecord
from datetime import datetime
from os.path import basename
from typing import List, Optional

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
        record.file = getattr(log_context_data, "file", None)
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
    def __init__(self, network=None, station_id=None, file=None):
        self.context: dict = dict(network=network, station_id=station_id, file=file)

    def __enter__(self):
        for key, val in self.context.items():
            if val :
                setattr(log_context_data, key, val)
        return self

    def __exit__(self, et, ev, tb):
        for key in self.context.keys():
            if self.context[key] and hasattr(log_context_data, key) :
                delattr(log_context_data, key)

        # In case of error, adds context to it
        if ev != None and not isinstance(ev, SystemExit):
            raise_from(Exception(
                "Exception: %s. Context : %s" % (str(ev), str(self.context))), ev)
            return True

class IgnoreAndLogExceptions(object):
    def __init__(self, network=None, station_id=None, file=None):
        pass

    def __enter__(self):
        pass

    def __exit__(self, et, ev, tb):
        if ev is not None:
            if isinstance(ev, KeyboardInterrupt) :
                # Don't capture Ctrl-C
                return False
            else:
                logger.error("Error happened. Ignoring it a continuing. %s", ev)
                logger.exception(ev)
                return True


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

        file=None
        if record.file :
            file = basename(record.file)

        log_renderable = self._log_render(
            self.console,
            [message_renderable] if not traceback else [message_renderable, traceback],
            log_time=log_time,
            time_format=time_format,
            level=level,
            path=file,
            line_no=None,
            link_path=record.pathname if self.enable_link_path else None,
        )
        return log_renderable

# Setup logger
if not sys.stdout.isatty():
    console = Console(
        file=sys.stdout,
        force_terminal=False,
        width=140)
else :
    console = None



rich_handler = RichHandlerContext(omit_repeated_times=False, console=console)
rich_handler.addFilter(ThreadingLocalContextFilter(["network", "station_id"]))
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



