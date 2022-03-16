from collections import OrderedDict
from datetime import timedelta
from logging import warn

import pandas as pd

from lib.common import GLOBAL_VAR, DIRECT_VAR, DIFFUSE_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR, WIND_SPEED_VAR, \
    WIND_DIRECTION_VAR
from lib.handlers.base_handler import InSituHandler
from lib.log import info, warning


def read_mesor(stream, na_values=[-999.0, -99.9, -10.0, -9999.0]):

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

        mapping = dict(
            ghi=GLOBAL_VAR,
            dni=DIRECT_VAR,
            dhi=DIFFUSE_VAR,
            t_air=TEMP_VAR,
            rh=HUMIDITY_VAR,
            bp=PRESSURE_VAR,
            ws=WIND_SPEED_VAR,
            wd=WIND_DIRECTION_VAR)

        data = data[list(mapping.keys())]
        data = data.rename(columns=mapping)

        tz = 0
        if 'timezone' in metadata :
            utc, tz = metadata['timezone'].split("+")
            tz = int(tz)

            if not utc == "UTC" :
                raise Exception('Unknown timezone : %s' %  metadata['timezone'])

        if tz != 0 :
            info("Applying timezone : %d", tz)
            data.index = data.index - timedelta(hours=tz)

        data.T2 = data.T2 + 273.15  # T2: °C -> K
        data.RH = data.RH / 100  # percent -> 1
        data.P = data.P * 100  # Pressure hPa->Pa

        return data

    def pattern(self):
        return "*{Station_ID}*.txt"

    def data_vars(self):
        """ @override """
        return [GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR, WIND_SPEED_VAR, WIND_DIRECTION_VAR]