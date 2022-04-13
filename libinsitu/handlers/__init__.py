from libinsitu.handlers import SAURAN
from libinsitu.handlers.ABOM import ABOMHandler
from libinsitu.handlers.BSRN import BSRNHandler
from libinsitu.handlers.NREL_MIDC import NRELHandler
from libinsitu.handlers.RAD import RADHandler
from libinsitu.handlers.SAURAN import SAURANHandler
from libinsitu.handlers.enerMENA import EnerMENAHandler
from libinsitu.handlers.base_handler import InSituHandler

# Static map of handlers
HANDLERS = {
    "BSRN" : BSRNHandler,
    "enerMENA" : EnerMENAHandler,
    "ABOM" : ABOMHandler,
    "SAURAN" : SAURANHandler,
    "NREL_MIDC" : NRELHandler,
    "SURFRAD" : RADHandler,
    "SOLRAD" : RADHandler
}

