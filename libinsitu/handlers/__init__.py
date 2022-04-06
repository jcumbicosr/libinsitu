from libinsitu.handlers import SAURAN
from libinsitu.handlers.ABOM import ABOMHandler
from libinsitu.handlers.BSRN import BSRNHandler
from libinsitu.handlers.SAURAN import SAURANHandler

# Static map of handlers
from libinsitu.handlers.base_handler import InSituHandler
from libinsitu.handlers.enerMENA import EnerMENAHandler

HANDLERS = {
    "BSRN" : BSRNHandler,
    "enerMENA" : EnerMENAHandler,
    "ABOM" : ABOMHandler,
    "SAURAN" : SAURANHandler
}

