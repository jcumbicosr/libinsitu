import pandas as pd

from libinsitu.common import GLOBAL_VAR, DIRECT_VAR, DIFFUSE_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR, parseTimezone
from libinsitu.handlers.base_handler import map_cols, InSituHandler, ZERO_DEG_K

MAPPING = dict(
    GHI_corr_Avg=GLOBAL_VAR,
    DNI_corr_Avg=DIRECT_VAR,
    DHI_corr_Avg=DIFFUSE_VAR,
    Tair_Avg=TEMP_VAR,
    RH_Avg=HUMIDITY_VAR,
    BP_CS100_Avg=PRESSURE_VAR)

NA_VALUES= [-7999.0]

class ESMAPHandler(InSituHandler) :

    def _read_chunk(self, stream):
        df = pd.read_csv(stream, header=1, parse_dates=['TMSTAMP'], index_col=0, na_values=NA_VALUES)
        df = map_cols(df, MAPPING)

        # Update Time according to timezone
        df.index -= parseTimezone(self.properties["Station_Timezone"])

        df[HUMIDITY_VAR] = df[HUMIDITY_VAR] / 100  # percent -> 1
        df[PRESSURE_VAR] = df[PRESSURE_VAR] * 100 # Pressure hPa->Pa
        df[TEMP_VAR] = df[TEMP_VAR] + ZERO_DEG_K  # T2: °C -> K

        return df


