

from libinsitu.common import GLOBAL_VAR, DIRECT_VAR, DIFFUSE_VAR
from libinsitu.handlers.base_handler import InSituHandler, map_cols
import pandas as pd

# The time base for all readings is South African Standard Time (SAST" \
# See : http://www.scielo.org.za/scielo.php?script=sci_arttext&pid=S1021-447X2015000100001
TIMEZONE=2

class SAURANHandler(InSituHandler) :

    def _read_chunk(self, stream) :

        GHI_Col = self.properties["Station_GHI_Col"]
        DHI_Col = self.properties["Station_DHI_Col"]
        DNI_Col = self.properties["Station_DNI_Col"]

        mapping = {
           DHI_Col: DIFFUSE_VAR,
           DNI_Col: DIRECT_VAR,
           GHI_Col: GLOBAL_VAR}

        data = pd.read_csv(
            stream,
            skiprows=[0, 2, 3],
            parse_dates=["TmStamp"], index_col="TmStamp", dayfirst=True,
            usecols=["TmStamp"] + [GHI_Col, DHI_Col, DNI_Col])


        data = map_cols(data, mapping)

        # Shift Timezone
        data.index -= pd.to_timedelta(TIMEZONE, "H")

        return data


    def data_vars(self):
        """ @override """
        return [GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR]
