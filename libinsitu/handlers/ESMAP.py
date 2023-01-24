import pandas as pd

from libinsitu.common import GLOBAL_VAR, DIRECT_VAR, DIFFUSE_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR, parseTimezone
from libinsitu.handlers.base_handler import map_cols, InSituHandler, ZERO_DEG_K

CSV_MAPPING = dict(
    GHI_corr_Avg=GLOBAL_VAR,
    DNI_corr_Avg=DIRECT_VAR,
    DHI_corr_Avg=DIFFUSE_VAR,
    Tair_Avg=TEMP_VAR,
    RH_Avg=HUMIDITY_VAR,
    BP_CS100_Avg=PRESSURE_VAR)

DAT_MAPPING = dict(
    Global_Avg=GLOBAL_VAR,
    Direct_Avg=DIRECT_VAR,
    Diffuse_Avg=DIFFUSE_VAR,
    AirTemp_Avg=TEMP_VAR,
    RH_Avg=HUMIDITY_VAR,
    Press_Avg=PRESSURE_VAR)

NA_VALUES= [-7999.0]

class ESMAPHandler(InSituHandler) :

    def __init__(self, properties):
        InSituHandler.__init__(self, properties, entries_extensions=[".dat", ".csv"])

    def _read_chunk(self, stream, entryname=""):
        if entryname.endswith("csv") :
            return self.csv_handler(stream)
        elif entryname.endswith("dat"):
            return self.dat_handler(stream)
        else:
            raise Exception("Bad extension for " + entryname)

    def csv_handler(self, stream):

        df = pd.read_csv(stream, header=1, parse_dates=['TMSTAMP'], index_col=0, na_values=NA_VALUES)
        df = map_cols(df, CSV_MAPPING)

        # Update Time according to timezone
        df.index -= parseTimezone(self.properties["Station_Timezone"])

        df[HUMIDITY_VAR] = df[HUMIDITY_VAR] / 100  # percent -> 1
        df[PRESSURE_VAR] = df[PRESSURE_VAR] * 100 # Pressure hPa->Pa
        df[TEMP_VAR] = df[TEMP_VAR] + ZERO_DEG_K  # T2: °C -> K

        return df

    def dat_handler(self, stream):

        df = pd.read_csv(stream, parse_dates=['TIMESTAMP'], index_col=0, skiprows=[0, 2, 3], na_values=NA_VALUES)
        df = map_cols(df, DAT_MAPPING)

        # Update Time according to timezone
        df.index -= parseTimezone(self.properties["Station_Timezone"])

        df[HUMIDITY_VAR] = df[HUMIDITY_VAR] / 100  # percent -> 1
        df[PRESSURE_VAR] = df[PRESSURE_VAR] * 100 # Pressure hPa->Pa
        df[TEMP_VAR] = df[TEMP_VAR] + ZERO_DEG_K  # T2: °C -> K

        return df


