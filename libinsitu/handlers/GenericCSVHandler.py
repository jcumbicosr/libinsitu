import os.path
from logging import  warning

import pandas as pd


from libinsitu.handlers.GenericHandler import GenericHandler


class GenericCSVHandler(GenericHandler) :
    """Generic handler for CSV,TSV and excel files """

    def __init__(self, *arg, **kwargs) :
        super(GenericCSVHandler, self).__init__(*arg, **kwargs)

    def _read_chunk(self, stream, entryname=None) :

        _, extension = os.path.splitext(entryname)
        extension = extension.lower()

        all_cols = self.time_mapping.cols()
        for var_mapping in self.var_mappings.values() :
            all_cols += var_mapping.cols()

        args = dict(
            usecols=all_cols,
            dtype=self._dtypes())

        if self.separator and extension == ".csv":
            args["sep"] = self.separator

        if self.skip_lines is not None :
            args["skiprows"] = self.skip_lines

        # Mapping done by index : no header, overriding it
        headers = self._generate_header()
        if headers :
            args["header"] = None
            args["names"] = list(headers.values())
            args["usecols"] = list(headers.keys())


        if extension == ".xlsx":
            df = pd.read_excel(stream, **args, engine='openpyxl')
        elif extension == ".xls" :
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