

from pvlib.iotools import parse_bsrn
from lib.common import GLOBAL_VAR, DIRECT_VAR, DIFFUSE_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR, DATA_VARS
from lib.handlers.base_handler import InSituHandler
from lib.log import error
import pandas as pd

class BSRNHandler(InSituHandler) :

    def _read_chunk(self, stream) :

        data, metadata = parse_bsrn(stream)

        mapping = dict(
            ghi=GLOBAL_VAR,
            dni=DIRECT_VAR,
            dhi=DIFFUSE_VAR,
            temp_air=TEMP_VAR,
            relative_humidity=HUMIDITY_VAR,
            pressure=PRESSURE_VAR)

        data = data[list(mapping.keys())]
        data = data.rename(columns=mapping)

        # Check type of column
        for col in DATA_VARS :
            if data[col].dtype == object :
                # String ? A couple of values might be incorrent.
                # Try to convert to float, ignoring errors
                error("Column %s parsed as String : converting to float. errors will be NaN", col)
                data[col] = pd.to_numeric(data[col], errors="coerce")

        # Convertions
        data.T2 = data.T2 + 273.15 # T2: °C -> K
        data.RH = data.RH / 100  # percent -> 1
        data.P = data.P * 100 # Pressure hPa->Pa

        return data

    def data_vars(self):
        """ @override """
        return [GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR]

    def pattern(self):
        return "{ID}{MM}{YY}*.dat.gz"