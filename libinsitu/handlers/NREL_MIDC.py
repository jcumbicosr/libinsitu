from pvlib.iotools.midc import MIDC_VARIABLE_MAP, TZ_MAP
from libinsitu.common import GLOBAL_VAR, DIRECT_VAR, DIFFUSE_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR, WIND_SPEED_VAR, \
    WIND_DIRECTION_VAR, NA_VALUES
from libinsitu.handlers.base_handler import InSituHandler, ZERO_DEG_K
import pandas as pd
from datetime import datetime, timedelta

from libinsitu.log import warning, info

VARIABLE_MAP = {
    'ghi' : GLOBAL_VAR,
    'dni' : DIRECT_VAR,
    'dhi' : DIFFUSE_VAR,
    'wind_speed' : WIND_SPEED_VAR,
    'temp_air' : TEMP_VAR,
    'relative_humidity': HUMIDITY_VAR}

TIME_FORMAT="%Y%j%H%M" # YYYYJJJHHMM
ONE_DAY = timedelta(days=1)

class NRELHandler(InSituHandler) :

    def _read_chunk(self, stream) :

        # Check file is not Error from REST API
        first_line = stream.readline()
        if first_line.startswith("Error") :
            return None

        stream.seek(0)

        # Count expected cols
        first_row = pd.read_csv(stream, nrows=0)
        col_length = len(first_row.columns)
        stream.seek(0)

        # CSV to pandas
        data = pd.read_csv(stream, usecols=range(col_length), na_values=NA_VALUES)
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

        #info("Columns : %s", columns)

        # Filter and rename columns
        data = data[list(mapping.keys())]
        data = data.rename(columns=mapping)

        columns = list(data.columns)

        if TEMP_VAR in data.columns :
            data[TEMP_VAR] = data[TEMP_VAR] + ZERO_DEG_K # T2: °C -> K

        if HUMIDITY_VAR in columns :
            data[HUMIDITY_VAR] = data[HUMIDITY_VAR] / 100  # percent -> 1

        return data


    def data_vars(self):
        """ @override """
        return [GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR, WIND_SPEED_VAR, WIND_DIRECTION_VAR]


def parseTime(yyyyjjjhhmm) :
    """ Parse time, handling corner case of H:24 """
    hh = yyyyjjjhhmm[7:9]
    plusDay = 0
    if hh == "24" :
        yyyyjjjhhmm = yyyyjjjhhmm[:7] + "00" + yyyyjjjhhmm[9:]
        plusDay = 1
    res = datetime.strptime(yyyyjjjhhmm, TIME_FORMAT)
    if plusDay > 0 :
        res += ONE_DAY
    return res


def tzCol(data) :
    tz_columns = list(str(col) for col in data.columns if len(str(col)) == 3 and str(col)[1:] == "ST")
    if len(tz_columns) > 1:
        raise Exception("Found more than 1 potential Timezone columns : %s" % str(tz_columns))
    if len(tz_columns) == 0:
        raise Exception("Found no  Timezone column")
    return tz_columns[0]

# Adapation of function from pvlib / midc to handle hour=24
def format_index_raw(data):
    """Create DatetimeIndex for the Dataframe localized to the timezone provided
    as the label of the third column.

    Parameters
    ----------
    data: Dataframe
        Must contain columns 'Year' and 'DOY'. Timezone must be found as the
        label of the third (time) column.

    Returns
    -------
    data: Dataframe
        The data with a Datetime index localized to the provided timezone.
    """


    # There shoulf be a single TZ column
    tz_raw = tzCol(data)

    timezone = TZ_MAP.get(tz_raw, tz_raw)
    year = data.Year.apply(str)
    jday = data.DOY.apply(lambda x: '{:03d}'.format(x))
    time = data[tz_raw].apply(lambda x: '{:04d}'.format(x))
    time_str = year + jday + time
    index = time_str.apply(parseTime)
    data = data.set_index(index)
    data = data.tz_localize(timezone)
    return data