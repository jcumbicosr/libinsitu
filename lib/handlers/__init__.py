from lib.handlers.ABOM import ABOMHandler
from lib.handlers.BSRN import BSRNHandler

# Static map of handlers
from lib.handlers.enerMENA import EnerMENAHandler

HANDLERS = {
    "BSRN" : BSRNHandler,
    "enerMENA" : EnerMENAHandler,
    "ABOM" : ABOMHandler
}

