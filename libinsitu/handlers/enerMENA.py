from collections import OrderedDict
from datetime import timedelta

import pandas as pd

from libinsitu.common import GLOBAL_VAR, DIRECT_VAR, DIFFUSE_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR, WIND_SPEED_VAR, \
    WIND_DIRECTION_VAR, NA_VALUES, parseTimezone
from libinsitu.handlers.base_handler import InSituHandler, ZERO_DEG_K
from libinsitu.log import info, warning


# Possible mapping
MAPPING = dict(
            ghi=GLOBAL_VAR,
            dni=DIRECT_VAR,
            dhi=DIFFUSE_VAR,
            GHI=GLOBAL_VAR,
            DNI=DIRECT_VAR,
            DHI=DIFFUSE_VAR,
            t_air=TEMP_VAR,
            rh=HUMIDITY_VAR,
            bp=PRESSURE_VAR,
            ws=WIND_SPEED_VAR,
            wd=WIND_DIRECTION_VAR)

def read_mesor(stream, na_values=NA_VALUES):

    metadata = {}  # Initilize dictionary containing metadata
    channels = OrderedDict()
    metadata["channels"] = channels


    FirstLine = str(stream.readline())

    if not 'MESOR' in FirstLine:
        raise Exception("This does not appear to be a MESOR file")

    line = ''

    while not ("#begindata" in line) :
        line = stream.readline()

        if ('#comment' in line) or  ('#begindata' in line) :
            continue

        line = line.strip("#")

        if line.startswith("channel") :
            parts = line.split(maxsplit=2)
            channels[parts[1].strip()] = parts[2].strip()
        else:
            parts = line.split(maxsplit=1)
            if len(parts) >= 2 :
                metadata[parts[0].strip()] = parts[1].strip()

    def safe_date(v) :
        return pd.to_datetime(v, errors="coerce")

    # Read data as CSV
    data = pd.read_csv(
        stream,
        header=None,
        delimiter='\t',
        comment='#',
        parse_dates=[0],
        index_col=0,
        na_values=na_values,
        date_parser=safe_date)

    # Bad dates ?
    nb_baddates = sum(data.index.isnull())
    if nb_baddates > 0 :
        warning("Skipping %d bad dates" % nb_baddates)
        data = data[data.index.notnull()]

    data.columns = list(channels.keys())[2:]

    return metadata, data

class EnerMENAHandler(InSituHandler) :

    def _read_chunk(self, stream):

        metadata, data = read_mesor(stream)

        keys = list(key for key in data.columns if key in MAPPING)
        mapping = {key: MAPPING[key] for key in keys}

        data = data[keys]
        data = data.rename(columns=mapping)

        tz = timedelta(hours=0)
        if 'timezone' in metadata :

            tz = parseTimezone(metadata['timezone'])

        if tz != timedelta(hours=0) :
            info("Applying timezone : %s", tz)
            data.index = data.index - tz

        # Convertions
        if TEMP_VAR in data :
            data[TEMP_VAR] = data[TEMP_VAR] + ZERO_DEG_K  # T2: °C -> K
        if HUMIDITY_VAR in data:
            data[HUMIDITY_VAR] = data[HUMIDITY_VAR] / 100  # percent -> 1
        if PRESSURE_VAR in data:
            data[PRESSURE_VAR] = data[PRESSURE_VAR] * 100  # Pressure hPa->Pa

        return data

    def data_vars(self):
        """ @override """
        return [GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR, WIND_SPEED_VAR, WIND_DIRECTION_VAR]