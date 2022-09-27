

from pvlib.iotools import parse_bsrn
from libinsitu.common import GLOBAL_VAR, DIRECT_VAR, DIFFUSE_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR, DATA_VARS
from libinsitu.handlers.base_handler import InSituHandler, map_cols, ZERO_DEG_K
from libinsitu.log import error
import pandas as pd

MAPPING = dict(
    ghi=GLOBAL_VAR,
    dni=DIRECT_VAR,
    dhi=DIFFUSE_VAR,
    temp_air=TEMP_VAR,
    relative_humidity=HUMIDITY_VAR,
    pressure=PRESSURE_VAR)

class BSRNHandler(InSituHandler) :

    def _read_chunk(self, stream) :

        data, metadata = parse_bsrn(stream)

        data = map_cols(data, MAPPING)

        # Check type of column
        for col in self.data_vars() :
            if data[col].dtype == object :
                # String ? A couple of values might be incorrent.
                # Try to convert to float, ignoring errors
                error("Column %s parsed as String : converting to float. errors will be NaN", col)
                data[col] = pd.to_numeric(data[col], errors="coerce")

        # Convertions
        data[TEMP_VAR] = data[TEMP_VAR] + ZERO_DEG_K # T2: °C -> K
        data[HUMIDITY_VAR] = data[HUMIDITY_VAR] / 100  # percent -> 1
        data[PRESSURE_VAR] = data[PRESSURE_VAR] * 100 # Pressure hPa->Pa

        return data

    def data_vars(self):
        """ @override """
        return [GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR]