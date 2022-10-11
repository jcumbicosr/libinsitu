import argparse
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import sg2
from netCDF4 import Dataset

from libinsitu import read_res, info, netcdf_to_dataframe, LATITUDE_VAR, LONGITUDE_VAR, ELEVATION_VAR, STATION_NAME_VAR, \
    datetime64_to_int, sec_to_datetime64, getTimeVar
from libinsitu.cdl import cdl2netcdf, parse_cdl
import pandas as pd
import numpy as np

from libinsitu.log import LogContext

INDEX_CDL = "index.cdl"

WRITE_LOCK = Lock

def parser() :

    parser = argparse.ArgumentParser(description='Produces daily index NetCDF files from other files')
    parser.add_argument('output', metavar='<out.nc>', help="Output NetCDF file")
    parser.add_argument('inputs', metavar='<file.nc>', help="Input NetCDF files", nargs="+")

    return parser


def main() :

    args = parser().parse_args()

    out_nc = Dataset(args.output, "w")

    properties = dict()

    # Init output NetCDF
    properties["NbStations"] = len(args.inputs)
    cdl = parse_cdl(read_res(INDEX_CDL), properties)
    cdl2netcdf(out_nc, cdl)

    # Open all input NetCDF (not expensive, since no data is read at this point)
    input_ncs = list(Dataset(input, "r") for input in args.inputs)

    start_time = min_time(input_ncs)
    start_day = datetime64_to_int(out_nc, start_time, 'D')

    def process_fn(args) :

        istation, (filename, input) = args

        with LogContext(file=filename):
            info("Processing %s" % filename)
            in_df = netcdf_to_dataframe(input)
            res = process_input(istation, out_nc, in_df)
            return istation, res



    # Parallel execution
    executor = ThreadPoolExecutor()

    # The computation is parallel
    # The write is sequential
    for istation, data_dic in executor.map(process_fn, enumerate(zip(args.inputs, input_ncs))) :
        for key, data in data_dic.items() :
            write_series(out_nc, istation, key, data, start_day)


    """for istation, (filename, input) in enumerate(zip(args.inputs, input_ncs)) :
        with LogContext(file=filename):
            info("Processing %s" % filename)
            in_df = netcdf_to_dataframe(input)
            process_input(istation, out, in_df, start_time)"""


def min_time(input_ncs) :
    res= None
    for input in input_ncs :
        start_date = sec_to_datetime64(input, getTimeVar(input)[0])
        if res is None or res > start_date :
            res = start_date
    return res

def process_input(istation, out_nc, in_df) :

    res = dict()

    lat = in_df.attrs[LATITUDE_VAR]
    lon = in_df.attrs[LONGITUDE_VAR]
    alt = in_df.attrs[ELEVATION_VAR]
    name = in_df.attrs[STATION_NAME_VAR]

    out_nc.variables[LATITUDE_VAR][istation] = lat
    out_nc.variables[LONGITUDE_VAR][istation] = lon
    out_nc.variables[ELEVATION_VAR][istation] = alt
    out_nc.variables[STATION_NAME_VAR][istation] = name

    # Compute a boolean index of daylight records
    toa = compute_toa(lat, lon, alt, in_df.index)
    is_daylight = toa.TOA > 0

    # Daily expected number of records
    expected_daylight_count = is_daylight.resample('D').sum()

    res["expected_daylight_count"] = expected_daylight_count
    #write_series(out_nc, istation,  "expected_daylight_count", expected_daylight_count, start_day)

    for col in in_df.columns :

        info("Processing for variable %s" % col)

        not_na = ~in_df[col].isna()

        valid_daylight = not_na & is_daylight

        if "QC" in in_df :
            info("with QC")
            valid_daylight = valid_daylight & (in_df.QC == 0)

        valid_daily = valid_daylight.resample('D').sum()

        #write_series(out_nc, istation, col + "_valid_daylight_count", valid_daily, start_day)
        res[col + "_valid_daylight_count"] = valid_daily

    return res


def write_series(out_nc, istation, var_name, series, ref_day) :

    time_var = getTimeVar(out_nc)

    # Fill holes / make time series regular
    series = series.asfreq("1D")

    nb_times = len(time_var)

    start_day = datetime64_to_int(out_nc, series.index.min(), 'D')
    end_day = datetime64_to_int(out_nc, series.index.max(), 'D')
    end_idx = end_day - ref_day

    if end_idx >= nb_times :
        time_var[0:end_idx+1] = np.arange(ref_day, end_day+1)

    if not var_name in out_nc.variables :
        out_nc.createVariable(
            var_name, np.int16, ["station", "time"],
            zlib=True,
            complevel=9,
            fill_value=-1)

    out_var = out_nc.variables[var_name]

    start_idx = start_day - ref_day

    out_var[istation, start_idx:] = series.values


def compute_toa(lat, lon, alt, times) :

    sun_pos = sg2.sun_position(
        [[lon, lat, alt]],
        times,
        ["topoc.toa_hi"])

    df = pd.DataFrame(dict(
        TOA=np.squeeze(sun_pos.topoc.toa_hi)),
        index=times)

    return df
