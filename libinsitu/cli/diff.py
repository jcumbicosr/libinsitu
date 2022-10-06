# Performs various checks on NetCDF files
import argparse
from netCDF4 import Dataset

from libinsitu import getStationId, getNetworkId
from libinsitu.common import netcdf_to_dataframe, GLOBAL_VAR, DIFFUSE_VAR, DIRECT_VAR, PRESSURE_VAR, \
    HUMIDITY_VAR, TEMP_VAR
from libinsitu.log import *
import numpy as np

NAN_VALUES = {
    GLOBAL_VAR : -999.0,
    DIFFUSE_VAR : -999.0,
    DIRECT_VAR : -999.0,
    TEMP_VAR : 173.25,
    HUMIDITY_VAR : -0.999,
    PRESSURE_VAR: -99900.0
}

CHUNK_SIZE = 100

def file2df(filename) :
    nc = Dataset(filename, mode='r')
    df = netcdf_to_dataframe(nc)
    nc.close()
    return df


def diff(df1, df2, args) :

    identical = True

    if len(df1.index) != len(df2.index) or not np.all(df1.index == df2.index) :
        identical = False
        warning("Timing differ : [%s|%s|%d] <-> [%s|%s|%d]",
                df1.index.min(), df1.index.max(), len(df1.index),
                df2.index.min(), df2.index.max(), len(df2.index))

    join = df1.join(df2, lsuffix="1", rsuffix="2", how="inner")

    cols1 = set(df1.columns)
    cols2 = set(df2.columns)

    if cols1 != cols2 :
        warning("datasets have different set of colums : %s <-> %s" % (",".join(cols1), ",".join(cols2)))

    common_cols = cols1 & cols2

    for col in common_cols :
        with LogContext(file=col) :

            data1 = join[col + "1"]
            data2 = join[col + "2"]

            # Check missing values
            for this, other, this_name, other_name in [(data1, data2, "data1", "data2"), (data2, data1, "data2", "data1")] :

                missing_idx = this.isna() & ~other.isna()
                missing_nb = sum(missing_idx)
                if missing_nb > 0:
                    missing_vals = other[missing_idx]
                    min_missing = min(missing_vals)
                    max_missing = max(missing_vals)

                    identical = False

                    missing_dates = join.index[missing_idx]

                    warning("%d NA values in %s only. Data values in %s : [%f:%f] from %s to %s",
                            missing_nb,
                            this_name,
                            other_name,
                            min_missing,
                            max_missing,
                            np.min(missing_dates),
                            np.max(missing_dates))


            # Check different values
            rmse = np.sqrt(np.mean((data1 - data2) ** 2))
            if rmse > 0 :
                identical = False
                warning("rmse:%f", rmse)

                nonna = ~data1.isna() & ~data2.isna()
                non_equal = nonna & ~np.isclose(data1, data2)
                diff_nb = sum(non_equal)

                if diff_nb > 0 :
                    identical = False

                    dates = join.index[non_equal]

                    warning("Different values in data1 and data2 : %d. From %s to %s",
                            diff_nb,
                            np.min(dates),
                            np.max(dates))

    if identical :
        info("The two datasets are identical")

def dump(df1, df2) :

    debug("Join")
    outer = df1.join(df2, lsuffix="1", rsuffix="2", how="outer")
    mask = np.zeros(outer.index.values.shape)

    for col in df1. columns :
        mask = mask | (outer[col+"1"] != outer[col+"2"])

    debug("Diff")
    diff = outer[mask]

    debug("Print")
    for i in range(0, diff.shape[0], CHUNK_SIZE) :
        chunk = diff[i:i+CHUNK_SIZE]
        chunk.to_string(sys.stdout, header=True, justify="left")
        print("\n")

def main() :

    parser = argparse.ArgumentParser(description='Transform In-Situ data into NetCDF files')
    parser.add_argument('file1', metavar='<file1.nc>', type=str, help='First NetCDF file')
    parser.add_argument('file2', metavar='<file2.nc>', type=str, help='Second NetCDF file')
    parser.add_argument('--dump', '-d', default=False, action='store_true',
                        help="Dump all diff in text format")
    args = parser.parse_args()

    df1 = file2df(args.file1)
    df2 = file2df(args.file2)

    # Replace nan values for df2
    for col, na_val in NAN_VALUES.items():
        if col not in df2 :
            continue
        vals = df2[col]
        idx = np.isclose(vals, na_val)
        df2[col][idx] = np.nan

    station_id = getStationId(df1.attrs)
    network = getNetworkId(df1.attrs)

    with LogContext(network=network, station_id=station_id, file="%s:%s" % (args.file1, args.file2)):

        if args.dump :
            dump(df1, df2)
        else:
            diff(df1, df2, args)


if __name__ == '__main__':
    main()
