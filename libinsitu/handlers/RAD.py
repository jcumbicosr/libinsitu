

from libinsitu.common import GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR, TEMP_VAR, WIND_SPEED_VAR, WIND_DIRECTION_VAR
from libinsitu.handlers.base_handler import map_cols, InSituHandler, ZERO_DEG_K

from pvlib.iotools import surfrad


class RADHandler(InSituHandler) :

    def read_chunk(self, filename:str, encoding='latin1'):
        """ @override """
        data, metadata = surfrad.read_surfrad(filename, map_variables=False)
        mapping = {
            "dw_solar" :  GLOBAL_VAR,
            "direct_n" : DIRECT_VAR,
            "diffuse" : DIFFUSE_VAR,
            "temp" : TEMP_VAR,
            "windspd" :  WIND_SPEED_VAR,
            "winddir" : WIND_DIRECTION_VAR}

        data = map_cols(data, mapping)

        # Conversions
        data[TEMP_VAR] = data[TEMP_VAR] + ZERO_DEG_K

        return data

    def data_vars(self):
        """ @override """
        return [GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR, TEMP_VAR, WIND_SPEED_VAR, WIND_DIRECTION_VAR]