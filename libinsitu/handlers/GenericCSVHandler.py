from libinsitu.handlers import InSituHandler
import json
import pandas as pd
import numpy as np


class Mapping() :
    def __init__(self, var_name, col) :
        # Might be a mapping in case of time var

        # If "col" is an index, take the varname as the column name
        self.col = var_name if isinstance(col, int) else col
        self.col_idx = (col - 1) if isinstance(col, int) else None

    def cols(self) :
        if isinstance(self.col, dict) :
            return list(self.col.values())
        else:
            return [self.col]

class TimeMapping(Mapping) :

    def __init__(self, js):

        self.format = None
        if not isinstance(js, dict):
            # Only name of target column
            super().__init__("time", js)
            return

        js = js.copy()

        if "format" in js :
            self.format = js["format"]
            del js["format"]

        if 'col' in js :
            super().__init__("time", js["col"])
        else:
            # No *name* column ? the rest is mapping of individual fields
            super().__init__("time", js)

    def parse_time(self, df):

        # Single column
        if isinstance(self.col, str):
            time = pd.to_datetime(
                df[self.col],
                format=self.format,
                infer_datetime_format=(self.format == None),
                errors="coerce")
        else:
            # 'col' is a map of time attribute => columns
            time = pd.to_datetime(
                dict((time_attr, df[col]) for time_attr, col in self.col.items()))

        df = df.drop(columns=self.cols())
        df["time"] = time
        df = df.set_index("time")

        return df


class VarMapping(Mapping) :

    def __init__(self, var_name, js):

        self.var_name = var_name
        self.scale = None
        self.offset = None

        if not isinstance(js, dict) :
            super().__init__(var_name, js)
            return

        super().__init__(var_name, js["col"])

        if "scale" in js :
            self.scale = js["scale"]

        if "offset" in js :
            self.offset = js["offset"]

    def parse_data(self, df):

        res = df[self.col]
        del df[self.col]

        if self.scale:
            res = res * self.scale
        if self.offset:
            res += self.offset

        df[self.var_name] = res
        return df


class GenericCSVHandler(InSituHandler) :

    def __init__(self, properties, mapping_file):
        with open(mapping_file, "r") as f:
            js = json.load(f)

        super().__init__(properties)

        mapping = js["mapping"]

        self.time_mapping = TimeMapping(mapping["time"])
        self.separator = js.get("separator", ",")

        del mapping["time"]
        self.var_mappings = {key: VarMapping(key, val) for key, val in mapping.items()}

    def _generate_header(self):
        """In case columns are expressed as indexes, generate the list of headers """
        if self.time_mapping.col_idx is None :
            # Ensure no mixed named and indexed cols
            if any(map.col_idx is not None for map in self.var_mappings.values()) :
                raise Exception("Cannot mix named and indexed columns")
            return None

        if any(map.col_idx is None for map in self.var_mappings.values()):
            raise Exception("Cannot mix named and indexed columns")

        res = dict()
        res[self.time_mapping.col_idx] = self.time_mapping.col
        for map in self.var_mappings.values():
            res[map.col_idx] = map.col

        # Return list of columns, sorted by idx
        return {idx:res[idx] for idx in sorted(res.keys())}

    def _dtypes(self) :
        dtypes = {k:str for k in self.time_mapping.cols()}
        for map in self.var_mappings.values() :
            dtypes[map.col] = np.float
        return dtypes

    def _read_chunk(self, stream, entryname=None) :

        all_cols = self.time_mapping.cols()
        for var_mapping in self.var_mappings.values() :
            all_cols += var_mapping.cols()

        args = dict(sep=self.separator,
            usecols=all_cols,
            dtype=self._dtypes())

        # Mapping done by index : no header, overriding it
        headers = self._generate_header()
        if headers :
            args["header"] = None
            args["names"] = list(headers.values())
            args["usecols"] = list(headers.keys())

        df = pd.read_csv(stream, **args)

        # Parse time and remove source columns
        df = self.time_mapping.parse_time(df)

        # Parse data
        for var_name, mapping in self.var_mappings.items() :
            df = mapping.parse_data(df)

        return df

    def data_vars(self):
        return list(self.var_mappings.keys())
