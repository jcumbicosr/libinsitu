import os.path
from libinsitu.log import info
from libinsitu.log import warning
import pandas as pd
import xarray as xr


from libinsitu.handlers.GenericHandler import GenericHandler


class GenericMappingHandler(GenericHandler) :
    """Generic handler for CSV,TSV and excel files """

    def __init__(self, *arg, **kwargs) :
        super(GenericMappingHandler, self).__init__(*arg, **kwargs)

    def read_chunk(self, filename:str, encoding='latin1') :
        """File level"""
        file, ext = os.path.splitext(filename)

        if ext == ".nc" :
            info(f"Detected NetCDF input file {filename}")
            return self.handle_netcdf(filename)

        return GenericHandler.read_chunk(self, filename, encoding)

    def _read_chunk(self, stream, entryname=None) :
        """Stream level (possibly within zip)"""

        _, extension = os.path.splitext(entryname)
        extension = extension.lower()

        all_cols = self.time_mapping.cols()
        for var_mapping in self.var_mappings.values():
            all_cols += var_mapping.cols()

        args = dict(
            usecols=all_cols,
            dtype=self._dtypes())

        if self.separator and extension == ".csv":
            args["sep"] = self.separator

        if self.skip_lines is not None:
            args["skiprows"] = self.skip_lines

        # Mapping done by index : no header, overriding it
        headers = self._generate_header()
        if headers:
            args["header"] = None
            args["names"] = list(headers.values())
            args["usecols"] = list(headers.keys())

        if extension == ".xlsx":
            df = pd.read_excel(stream, **args, engine='openpyxl')
        elif extension == ".xls":
            df = pd.read_excel(stream, **args, engine="xlrd")
        elif extension == ".csv":
            df = pd.read_csv(stream, **args)
        elif extension == ".tsv":
            if not "sep" in args:
                args["sep"] = "\t"
            df = pd.read_csv(stream, **args)
        else:
            warning(f"Unkown extension {extension}. Assuming CSV like")
            df = pd.read_csv(stream, **args)

        # Parse time and remove source columns
        df = self.time_mapping.parse_time(df)

        df = self._transform(df)

        return df


    def handle_netcdf(self, filename):

        ds = xr.open_dataset(filename)

        time_cols = self.time_mapping.cols()

        assert len(time_cols) == 1, "Single time column required for NetCDF reader"

        cols_data = dict(time=ds[time_cols[0]])
        for mapping in self.var_mappings.values():
            col = mapping.col
            cols_data[col] = ds[col].values.flatten()

        df = pd.DataFrame(cols_data).set_index("time")

        # Map to output Dataframe
        df = self._transform(df)

        return df