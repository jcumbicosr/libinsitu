

from libinsitu.common import GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR, TEMP_VAR, WIND_SPEED_VAR, WIND_DIRECTION_VAR
from libinsitu.handlers.base_handler import map_cols, InSituHandler, ZERO_DEG_K

from pvlib.iotools import solrad


class SOLRADHandler(InSituHandler) :

    def read_chunk(self, filename:str, encoding='latin1'):
        """ @override """
        data = solrad.read_solrad(filename)
        mapping = {
            "ghi" :  GLOBAL_VAR,
            "dni" : DIRECT_VAR,
            "dhi" : DIFFUSE_VAR}

        data = map_cols(data, mapping)

        return data

    def data_vars(self):
        """ @override """
        return [GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR]