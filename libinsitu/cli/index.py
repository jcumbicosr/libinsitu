import argparse
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from multiprocessing import Lock

import sg2
from netCDF4 import Dataset

from libinsitu import read_res, info, netcdf_to_dataframe, LATITUDE_VAR, LONGITUDE_VAR, ELEVATION_VAR, STATION_NAME_VAR, \
    datetime64_to_sec, sec_to_datetime64, getTimeVar, TIME_DIM, QC_FLAGS_VAR, qc_masks
from libinsitu.cdl import cdl2netcdf, parse_cdl
import pandas as pd
import numpy as np

from libinsitu.log import LogContext

INDEX_CDL = "index.cdl"

WRITE_LOCK = Lock()

EXPECTED_COUNT_VAR = "expected_daylight_count"
VALID_COUNT_SUFFIX = "_valid_daylight_count"
QC_COUNT_PATTTERN = QC_FLAGS_VAR + "_%s_daylight_count"

def parser() :

    parser = argparse.ArgumentParser(description='Produces daily index NetCDF files from other files')
    parser.add_argument('output', metavar='<out.nc>', help="Output NetCDF file")
    parser.add_argument('inputs', metavar='<file.nc>', help="Input NetCDF files", nargs="+")
    parser.add_argument('--max-threads', metavar='<nb_threads>', type=int, default=None)

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

    # Gather all data vars
    data_vars = set()
    for input_nc in input_ncs :
        data_vars = data_vars.union(list_data_vars(input_nc))

    # Create all vars upfront
    create_count_var(out_nc, EXPECTED_COUNT_VAR)
    for varname in data_vars:
        create_count_var(out_nc, varname + VALID_COUNT_SUFFIX)

    # Init QC flags if any
    for input_nc in input_ncs :
        if QC_FLAGS_VAR in input_nc.variables:
            qc_var = input_nc.variables[QC_FLAGS_VAR]
            for flag in qc_var.flag_meanings.split() :
                create_count_var(out_nc, QC_COUNT_PATTTERN % flag)
            break

    start_time = min_time(input_ncs)
    start_day = datetime64_to_sec(out_nc, start_time, 'D')

    # Close output to allow multi process
    out_nc.close()

    # Parallel execution
    executor = ProcessPoolExecutor(max_workers=args.max_threads)
    res = executor.map(
        partial(process_station, start_day, args.output),
        range(len(args.inputs)), # istation
        args.inputs) # infile
    list(res)


def min_time(input_ncs) :
    res= None
    for input in input_ncs :
        start_date = sec_to_datetime64(input, getTimeVar(input)[0])
        if res is None or res > start_date :
            res = start_date
    return res

def process_station(start_day, outfile, istation, infile) :

    with LogContext(file=infile) :

        in_dfs = netcdf_to_dataframe(infile, chunked=True, chunk_size=1000000)

        # Use chunked processing to reduce memory usage
        for ichunk, in_df in enumerate(in_dfs):

            chunk_id = "#%d %s -> %s" % (ichunk, in_df.index.min(), in_df.index.max())

            info("Processing %s. Chunk %s" % (infile, chunk_id))

            # First compute data and then write it all at once
            data_dic = dict()

            lat = in_df.attrs[LATITUDE_VAR]
            lon = in_df.attrs[LONGITUDE_VAR]
            alt = in_df.attrs[ELEVATION_VAR]
            name = in_df.attrs[STATION_NAME_VAR]

            # Compute a boolean index of daylight records
            toa = compute_toa(lat, lon, alt, in_df.index)
            is_daylight = toa.TOA > 0

            # Daily expected number of records
            expected_daylight_count = is_daylight.resample('D').sum()

            data_dic[EXPECTED_COUNT_VAR] = expected_daylight_count

            for col in in_df.columns :

                if col == QC_FLAGS_VAR :
                    continue

                #info("Processing for variable %s %s" % (col, "(with QC)" if QC_FLAGS_VAR in in_df else ""))

                not_na = ~in_df[col].isna()

                valid_daylight = not_na & is_daylight

                if QC_FLAGS_VAR in in_df :
                    valid_daylight = valid_daylight & (in_df.QC == 0)

                valid_daily = valid_daylight.resample('D').sum()

                #write_series(out_nc, istation, col + "_valid_daylight_count", valid_daily, start_day)
                data_dic[col + VALID_COUNT_SUFFIX] = valid_daily

            # QC
            if QC_FLAGS_VAR in in_df :
                qc_col = in_df[QC_FLAGS_VAR]
                for flag, mask in qc_masks(in_df).items() :
                    data_dic[QC_COUNT_PATTTERN % flag] = is_daylight & ((qc_col & mask) != 0)

            with WRITE_LOCK :

                info("Writing output for chunk %s" % chunk_id)

                out_nc = Dataset(outfile, mode="a")
                try:

                    # Write meta data
                    out_nc.variables[LATITUDE_VAR][istation] = lat
                    out_nc.variables[LONGITUDE_VAR][istation] = lon
                    out_nc.variables[ELEVATION_VAR][istation] = alt
                    out_nc.variables[STATION_NAME_VAR][istation] = name

                    # write data
                    for key, data in data_dic.items() :
                        write_series(out_nc, istation, key, data, start_day)
                finally:
                    out_nc.close()




def list_data_vars(ncfile) :
    res = set()
    timeVar = getTimeVar(ncfile)
    for varname, var in ncfile.variables.items() :
        if TIME_DIM in var.dimensions and var != timeVar and varname != QC_FLAGS_VAR :
            res.add(varname)
    return res

def create_count_var(ncfile, name):
        info("Adding var : %s" % name)
        ncfile.createVariable(
            name, int, ["station", "time"],
            zlib=True,
            complevel=9,
            fill_value=-1)

def write_series(out_nc, istation, var_name, series, ref_day) :

    time_var = getTimeVar(out_nc)

    # Fill holes / make time series regular
    series = series.asfreq("1D")

    nb_times = len(time_var)

    start_day = datetime64_to_sec(out_nc, series.index.min(), 'D')
    end_day = datetime64_to_sec(out_nc, series.index.max(), 'D')
    end_idx = end_day - ref_day

    if end_idx >= nb_times :
        time_var[0:end_idx+1] = np.arange(ref_day, end_day+1)



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
