

import pandas as pd

from pandas import DataFrame

from libinsitu.common import GLOBAL_VAR
from libinsitu.handlers.base_handler import InSituHandler, map_cols

MAPPING = dict(Gg_pyr=GLOBAL_VAR)

class ISEPVLive(InSituHandler) :

    def _read_chunk(self, stream) -> DataFrame:
        data = pd.read_csv(stream,sep='\t',parse_dates=['datetime'],index_col=0)
        data = map_cols(data, MAPPING)
        return data
