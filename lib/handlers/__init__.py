from typing import Dict

from lib.handlers import SAURAN
from lib.handlers.ABOM import ABOMHandler
from lib.handlers.BSRN import BSRNHandler
from lib.handlers.SAURAN import SAURANHandler

# Static map of handlers
from lib.handlers.base_handler import InSituHandler
from lib.handlers.enerMENA import EnerMENAHandler

HANDLERS = {
    "BSRN" : BSRNHandler,
    "enerMENA" : EnerMENAHandler,
    "ABOM" : ABOMHandler,
    "SAURAN" : SAURANHandler
}

