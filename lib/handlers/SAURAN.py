

from pvlib.iotools import parse_bsrn
from lib.common import GHI_VAR, DIR_VAR, DIF_VAR, TEMP_VAR, HUMIDITY_VAR, PRESSURE_VAR, DATA_VARS
from lib.handlers.base_handler import InSituHandler
from lib.log import error
import pandas as pd

class ABOMHandler(InSituHandler) :

    def _read_chunk(self, stream) :


        GHI_Col = self.properties["GHI_Col"]
        DHI_Col = self.properties["DHI_Col"]
        DNI_Col = self.properties["DNI_Col"]

        mapping = {
           DHI_Col : DIF_VAR,
           DNI_Col : DIR_VAR,
        GHI_Col: GHI_VAR}

        data = pd.read_csv(stream, skiprows=[0, 2, 3], parse_dates=["TmStamp"],
                    index_col="TmStamp", usecols=["TmStamp"] + [GHI_Col, DHI_Col, DNI_Col])

        data = data[list(mapping.keys())]
        data = data.rename(columns=mapping)

        return data


    def data_vars(self):
        """ @override """
        return [GHI_VAR, DIF_VAR, DIR_VAR]

    def pattern(self):
        return "{ID}_minute_{YYYY}{MM}.csv"