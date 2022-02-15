

from lib.common import GHI_VAR, DIR_VAR, DIF_VAR
from lib.handlers.base_handler import InSituHandler
import pandas as pd

# The time base for all readings is South African Standard Time (SAST" \
# See : http://www.scielo.org.za/scielo.php?script=sci_arttext&pid=S1021-447X2015000100001
TIMEZONE=2

class SAURANHandler(InSituHandler) :

    def _read_chunk(self, stream) :


        GHI_Col = self.properties["GHI_Col"]
        DHI_Col = self.properties["DHI_Col"]
        DNI_Col = self.properties["DNI_Col"]

        mapping = {
           DHI_Col : DIF_VAR,
           DNI_Col : DIR_VAR,
        GHI_Col: GHI_VAR}

        data = pd.read_csv(
            stream,
            skiprows=[0, 2, 3],
            parse_dates=["TmStamp"], index_col="TmStamp", dayfirst=True,
            usecols=["TmStamp"] + [GHI_Col, DHI_Col, DNI_Col])

        data = data[list(mapping.keys())]
        data = data.rename(columns=mapping)

        #
        data.index -= pd.to_timedelta(TIMEZONE, "H")

        return data


    def data_vars(self):
        """ @override """
        return [GHI_VAR, DIF_VAR, DIR_VAR]

    def pattern(self):
        return "{ID}_minute_{YYYY}{MM}.csv"