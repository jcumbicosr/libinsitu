from pvlib.iotools.bsrn import read_bsrn
from lib.common import GHI_VAR, DIR_VAR, DIF_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR
from lib.handlers.base_handler import InSituHandler


class BSRNHandler(InSituHandler) :

    def read_chunk(self, filename) :

        data, metadata = read_bsrn(filename)

        mapping = dict(
            ghi = GHI_VAR,
            dni = DIR_VAR,
            dhi = DIF_VAR,
            temp_air = TEMP_VAR,
            relative_humidity = HUMIDITY_VAR,
            pressure = PRESSURE_VAR)

        data = data[list(mapping.keys())]
        data = data.rename(columns=mapping)

        # Convertions
        data.T2 = data.T2 + 273.15 # T2: °C -> K
        data.RH = data.RH / 100  # percent -> 1
        data.P = data.P * 100 # Pressure hPa->Pa

        return data