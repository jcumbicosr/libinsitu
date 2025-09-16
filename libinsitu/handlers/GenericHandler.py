import json
import os.path
from logging import warn, warning
from os import path

import numpy as np
import pandas as pd

from libinsitu import NA_VALUES
from libinsitu.cdl import replace_placeholders
from libinsitu.handlers import InSituHandler
from dateutil.parser import parse
import re
import yaml


class Mapping():
    def __init__(self, var_name, js) :
        # Might be a mapping in case of time var

        # If "col" is an index, take the varname as the column name
        self.col = var_name if isinstance(js, int) else js
        self.col_idx = (js - 1) if isinstance(js, int) else None

    def cols(self) :
        if not isinstance(self.col, list) :
            return [self.col]
        else:
            return self.col.copy()

class TimeMapping(Mapping) :

    def __init__(self, js):

        self.format = None
        self.timezone = None

        if not isinstance(js, dict):
            # Only name of target column
            super().__init__("time", js)
            return

        js = js.copy()

        if "format" in js :
            self.format = js["format"]
            del js["format"]

        if "timezone" in js :
            self.timezone = js["timezone"]
            del js["timezone"]

        super().__init__("time", js["col"])


    def parse_time(self, df):

        # Several columns
        if isinstance(self.col, list):
            time_str = df[self.col].T.agg(' '.join)
        # Single column
        else:
            time_str = df[self.col]

        time = pd.to_datetime(
            time_str,
            format=self.format,
            infer_datetime_format=(self.format == None),
            errors="coerce")

        # Add timzone as suffix
        if self.timezone:
            tz = parse_tz(self.timezone)
            time = time.dt.tz_localize(tz).dt.tz_convert("UTC")

        # All errors ?
        if time.isna().sum() == len(time_str) :
            raise Exception("All time parsing failed. Example time str : '%s'. format:'%s'"% (time_str.values[0], self.format))


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

        res = res.astype(float)

        # FIXME make it configurable
        for na_val in NA_VALUES :
            res[res==na_val] = np.nan

        if self.scale:
            res = res * self.scale
        if self.offset:
            res += self.offset

        df[self.var_name] = res
        return df


def replace_placeholders_rec(js, properties):
    """Recursively replaces {placeholders} in js"""
    if isinstance(js, dict):
        return {key : replace_placeholders_rec(val, properties) for key, val in js.items()}
    elif isinstance(js, list):
        return [replace_placeholders_rec(val, properties) for val in js]
    elif isinstance(js, str) :
        return replace_placeholders(js, properties)
    else:
        return js


class GenericHandler(InSituHandler) :
    """Abstract generic class for hanlder taking a mapping file as input """

    def __init__(self, properties, mapping_file):

        super().__init__(properties, binary=True)

        with open(mapping_file, "r") as f:
            _, ext = path.splitext(mapping_file)

            if ext == ".json":
                js = json.load(f)
            elif ext in  [".yaml", "yml"] :
                js = yaml.safe_load(f)

        js = replace_placeholders_rec(js, properties)

        mapping = js["mapping"]

        # Read file pattern form config file
        self.file_pattern = js.get("file_pattern", "*.*")

        self.time_mapping = TimeMapping(mapping["time"])
        self.separator = js.get("separator", ",")
        self.comment = js.get("comment", None)
        self.skip_lines = js.get("skip_lines", None)
        self.encoding = js.get("encoding", None)

        if isinstance(self.skip_lines, list) :
            self.skip_lines = [i-1 for i in self.skip_lines]

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
            dtypes[map.col] = float
        return dtypes

    def _transform(self, df):
        """ Transform loaded Dataframe according to mapping """
        for var_name, mapping in self.var_mappings.items() :
            df = mapping.parse_data(df)
        return df



    def data_vars(self):
        return list(self.var_mappings.keys())

    def pattern(self):
        return self.file_pattern


def parse_tz(tz) :

    # See https://github.com/dateutil/dateutil/issues/70
    date_str = re.sub(r'(?:GMT|UTC)([+\-]\d+)', r'\1', f'2000-01-01 00:00 {tz}')
    date = parse(date_str)
    return date.tzinfo