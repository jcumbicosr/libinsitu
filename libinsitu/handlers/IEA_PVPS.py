from libinsitu import NA_VALUES
from libinsitu.handlers.base_handler import InSituHandler
import pandas as pd
from libinsitu.log import info, debug

DATE_COLS = dict(
    year='Year',
    month='Month',
    day='Day',
    hour='Hour',
    minute='Minute')

class IEA_PVPSHandler(InSituHandler) :

    def _read_chunk(self, stream):
        df = pd.read_csv(stream, comment="#", na_values=NA_VALUES)

        df["time"] = pd.to_datetime(dict((key, df[val]) for key, val in DATE_COLS.items()))
        df = df.drop(columns=list(DATE_COLS.values()))
        df = df.set_index("time")

        debug(df)

        return df

