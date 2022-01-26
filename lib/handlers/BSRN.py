from pvlib.iotools import parse_bsrn
from lib.common import GHI_VAR, DIR_VAR, DIF_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR
from lib.handlers.base_handler import InSituHandler


class BSRNHandler(InSituHandler) :

    def _read_chunk(self, stream) :

        data, metadata = parse_bsrn(stream)



        # Convertions
        data.T2 = data.T2 + 273.15 # T2: °C -> K
        data.RH = data.RH / 100  # percent -> 1
        data.P = data.P * 100 # Pressure hPa->Pa

        return data