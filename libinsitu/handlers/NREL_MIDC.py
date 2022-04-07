from logging import warn

from pvlib.iotools.midc import format_index_raw, MIDC_VARIABLE_MAP
from libinsitu.common import GLOBAL_VAR, DIRECT_VAR, DIFFUSE_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR, DATA_VARS, \
    TIME_VAR, WIND_SPEED_VAR, WIND_DIRECTION_VAR
from libinsitu.handlers.base_handler import InSituHandler
import pandas as pd

from libinsitu.log import warning, info

VARIABLE_MAP = {
    'ghi' : GLOBAL_VAR,
    'dni' : DIRECT_VAR,
    'dhi' : DIFFUSE_VAR,
    'wind_speed' : WIND_SPEED_VAR,
    'temp_air' : TEMP_VAR,
    'relative_humidity': HUMIDITY_VAR}

class NRELHandler(InSituHandler) :

    def _read_chunk(self, stream) :

        # CSV to pandas
        data = pd.read_csv(stream)
        data = format_index_raw(data).tz_convert("UTC")

        station_id = self.properties["Station_ID"]

        if not station_id in MIDC_VARIABLE_MAP :
            raise Exception("Station %s not defined in variable maps (%s)" % (station_id, list(MIDC_VARIABLE_MAP.keys())))

        # Transform variable map to our variable names
        mapping = MIDC_VARIABLE_MAP[station_id]
        mapping = {key: VARIABLE_MAP[val] for key, val in mapping.items()}

        # Filter only the columns that we can find
        columns = list(data.columns)
        for key in list(mapping.keys()) :
            if not key in columns :
                warning("Column %s was not found in dataset", key)
                del mapping[key]

        info("Columns : %s", columns)

        # Filter and rename columns
        data = data[list(mapping.keys())]
        data = data.rename(columns=mapping)

        if TEMP_VAR in columns :
            data[TEMP_VAR] = data[TEMP_VAR] + 273.15 # T2: °C -> K

        if HUMIDITY_VAR in columns :
            data[HUMIDITY_VAR] = data[HUMIDITY_VAR] / 100  # percent -> 1

        return data


    def data_vars(self):
        """ @override """
        return [GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR, WIND_SPEED_VAR, WIND_DIRECTION_VAR]

    def pattern(self):
        return "{Station_ID}-{YYYY}-{MM}.csv.gz"