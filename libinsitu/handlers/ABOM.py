import pandas as pd

from libinsitu.common import GLOBAL_VAR, DIRECT_VAR, DIFFUSE_VAR, parseTimezone
from libinsitu.handlers.base_handler import InSituHandler


class ABOMHandler(InSituHandler) :

    def _read_chunk(self, stream, entryname=None) :

        def date_parser(years, months, days, hours, minutes):
            strs = years + "/" + months + "/" + days + " " + hours + ":" + minutes
            return pd.to_datetime(strs)

        data = pd.read_csv(
            stream, skipinitialspace=True)
        
        data.index = date_parser(data.iloc[:, 2].astype(str), 
                                 data.iloc[:, 3].astype(str), 
                                 data.iloc[:, 4].astype(str), 
                                 data.iloc[:, 5].astype(str), 
                                 data.iloc[:, 6].astype(str)
                                 )
        data.index.name = "datetime"
        # Drop the columns we just used (indices 2, 3, 4, 5, 6)
        cols_to_drop = data.columns[[2, 3, 4, 5, 6]]
        data.drop(columns=cols_to_drop, inplace=True)

        ghi_col = data.columns[2]
        dir_col = data.columns[7]
        dif_col = data.columns[12]

        mapping = {
            ghi_col:GLOBAL_VAR,
            dir_col:DIRECT_VAR,
            dif_col:DIFFUSE_VAR}

        data = data[list(mapping.keys())]
        data = data.rename(columns=mapping)

        # Apply timezone
        data.index -= parseTimezone(self.properties["Station_Timezone"])

        return data

    def data_vars(self):
        """ @override """
        return [GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR]
