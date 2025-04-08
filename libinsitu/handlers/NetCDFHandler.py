import pandas as pd
import xarray as xr

from libinsitu.catalog import list_dataset_urls
from libinsitu.handlers.GenericHandler import GenericHandler


class NetCDFHandler(GenericHandler) :
    """Generic handler for CSV,TSV and excel files """

    def __init__(self, *arg, **kwargs) :
        super(NetCDFHandler, self).__init__(*arg, **kwargs)

    def read_chunk(self, filename:str, encoding=None):

        ds = xr.open_dataset(filename)

        time_cols = self.time_mapping.cols()

        assert len(time_cols) == 1, "Single time column required for NetCDF reader"

        cols_data = dict(time = ds[time_cols[0]])
        for mapping in self.var_mappings.values() :
            col = mapping.col
            cols_data[col] = ds[col].values.flatten()

        df = pd.DataFrame(cols_data).set_index("time")

        # Map to output Dataframe
        df = self._transform(df)

        return df

