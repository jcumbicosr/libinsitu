import pandas as pd

from libinsitu.common import GLOBAL_VAR, DIRECT_VAR, DIFFUSE_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR, parseTimezone
from libinsitu.handlers.base_handler import map_cols, InSituHandler, ZERO_DEG_K
import numpy as np
from libinsitu.log import warning

MAPPINGS = {
    GLOBAL_VAR : ["Global_Avg", "GHI_corr_Avg", "GHI1_corr_Avg", "GHI"],
    DIRECT_VAR : ["Direct_Avg", "DNI_corr_Avg", "DNI1_corr_Avg", "DNI"],
    DIFFUSE_VAR : ["Diffuse_Avg", "DHI_corr_Avg", "DHI1_corr_Avg", "DHI"],
    TEMP_VAR : ["AirTemp_Avg", "Tair_Avg", "T_amb"],
    HUMIDITY_VAR : ["RH_Avg", "RH"],
    PRESSURE_VAR : ["BP_CS100_Avg", "BP_CS100", "Press_Avg", "BP"]
}

NA_VALUES= [-7999.0, "NAN"]

class ESMAPHandler(InSituHandler) :

    def __init__(self, properties):
        InSituHandler.__init__(self, properties, entries_extensions=[".dat", ".csv"])

    def _read_chunk(self, stream, entryname=""):

        if self.properties["Station_Country"] == "Tanzania" :
            # Custom parser for DAR // any tanzania ?
            df = self.tan_csv_handler(stream)

        elif entryname.endswith("csv") :
            df = self.csv_handler(stream)

        elif entryname.endswith("dat"):
            df = self.dat_handler(stream)
        else:
            raise Exception("Bad extension for " + entryname)

        df = self.dynamic_mapping(df)

        # Update Time according to timezone
        df.index -= parseTimezone(self.properties["Station_Timezone"])

        df = df.apply(pd.to_numeric, axis=0, errors='coerce')

        df[HUMIDITY_VAR] = df[HUMIDITY_VAR] / 100  # percent -> 1
        df[PRESSURE_VAR] = df[PRESSURE_VAR] * 100  # Pressure hPa->Pa
        df[TEMP_VAR] = df[TEMP_VAR] + ZERO_DEG_K  # T2: °C -> K

        return df

    def dynamic_mapping(self, df):
        mapping = dict()
        for target, cols in MAPPINGS.items() :
            for col in cols :
                if col in df :
                    mapping[col] = target

        return map_cols(df, mapping)

    def csv_handler(self, stream):

        df = pd.read_csv(
            stream, header=1, index_col='TMSTAMP',
            na_values=NA_VALUES, on_bad_lines="skip")

        dates = pd.to_datetime(df.index, errors="coerce")

        nan_dates = pd.isna(dates)

        # If nan dates, warn and filter out
        if np.sum(nan_dates) > 0 :
            warning("Error parsing %d dates : skippings" % np.sum(nan_dates))
            df = df[~nan_dates]
            dates = dates[~nan_dates]

        df.index = dates

        return df

    def dat_handler(self, stream):

        df = pd.read_csv(
            stream, parse_dates=['TIMESTAMP'], index_col=0, skiprows=[0, 2, 3],
            na_values=NA_VALUES, on_bad_lines="skip")
        return df

    def tan_csv_handler(self, stream):

        df = pd.read_csv(stream, sep=";", na_values=NA_VALUES, on_bad_lines="skip")
        df[["hour", "minute"]] = df.Local_time.str.split(":", expand=True)


        datetimes = pd.to_datetime(df[["Year", "Month", "Day", "hour", "minute"]], errors="coerce")
        df.index = datetimes

        return df


