# -*- coding: utf-8 -*-
"""
Created on Thu Sep  8 12:59:01 2022

@author: y-m.saint-drenan
"""
import os
import pandas as pd
import copy
import numpy as np
from datetime import datetime

from dateutil.relativedelta import relativedelta

from .base_handler import InSituHandler
from libinsitu.log import info, debug
from ..common import GLOBAL_VAR, DIRECT_VAR, parseTimezone

IRRADIANCE_COL="Irradiance(W/m2)"



class SkyNetHandler(InSituHandler) :

    def _read_chunk(self, stream):

        out_col, year = read_header(stream)

        df = pd.read_csv(stream, sep=" ")

        # SKYNET data are every 10 seconds
        # They are offset by 2 seconds to "round" seconds
        # We offset them to round seconds
        df["time"] = pd.to_datetime(dict(
            year=year,
            month=df['Month'],
            day=df['Day']
        )) + pd.to_timedelta((df["Hour"] * 360).round() * 10, unit="seconds")

        df = df.rename(columns={IRRADIANCE_COL: out_col})
        df = df.set_index("time")

        # Apply timezone
        df.index -= parseTimezone(self.properties["Station_Timezone"])

        debug(df.tail())

        return df[[out_col]]


def read_header(stream) :

    out_col = None
    year = None

    # Parse header
    for line in stream:

        line = line.decode()

        # File type
        if "irradiance" in line:
            if "global" in line:
                out_col = GLOBAL_VAR
            elif "direct" in line:
                out_col = DIRECT_VAR

        # Year
        if "Year" in line:
            key, year = line.split(":")
            year = int(year.strip())

        # End of header
        if line.startswith("------"):
            return out_col, year

