from libinsitu.handlers import SAURAN, SKYNET
from libinsitu.handlers.ABOM import ABOMHandler
from libinsitu.handlers.BSRN import BSRNHandler
from libinsitu.handlers.ESMAP import ESMAPHandler
from libinsitu.handlers.IEA_PVPS import IEA_PVPSHandler
from libinsitu.handlers.ISE_PVLive import ISEPVLive
from libinsitu.handlers.NREL_MIDC import NRELHandler
from libinsitu.handlers.RAD import RADHandler
from libinsitu.handlers.SAURAN import SAURANHandler
from libinsitu.handlers.SKYNET import SkyNetHandler
from libinsitu.handlers.enerMENA import EnerMENAHandler
from libinsitu.handlers.base_handler import InSituHandler

# Static map of handlers
HANDLERS = {
    "BSRN" : BSRNHandler,
    "enerMENA" : EnerMENAHandler,
    "ABOM" : ABOMHandler,
    "ESMAP": ESMAPHandler,
    "ISE_PVLive" : ISEPVLive,
    "SAURAN" : SAURANHandler,
    "NREL_MIDC" : NRELHandler,
    "SURFRAD" : RADHandler,
    "SOLRAD" : RADHandler,
    "SKYNET" : SkyNetHandler,
    "IEA_PVPS" : IEA_PVPSHandler
}

def listNetworks() :
    return sorted(list(HANDLERS.keys()))

