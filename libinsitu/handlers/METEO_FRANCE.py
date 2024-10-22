

import pandas as pd

from libinsitu.common import GLOBAL_VAR, DIRECT_VAR, DIFFUSE_VAR
from libinsitu.handlers.base_handler import InSituHandler


class MeteoFranceHandler(InSituHandler) :

    def _read_chunk(self, stream, entryname=None) :

        data = pd.read_csv(stream, parse_dates=["time"], index_col="time", sep=",")
        data.loc[:, "GHI"] = data.GHI / 60
        return data


    def data_vars(self):
        """ @override """
        return [GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR]
