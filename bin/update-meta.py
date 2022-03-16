#!/usr/bin/env python
import datetime
import os.path
import sys

import numpy as np
from netCDF4 import Dataset

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from lib.handlers import HANDLERS
from process import init_nc, getProperties, readShortname, update_time_range, FIRST_DATA_ATT, LAST_DATA_ATT
import argparse

CHUNK_SIZE = 10000

def update_times(nc, ncvar, dry_run=False) :

    def process_chunk(start, stop, key) :
        data = ncvar[start:stop]
        if np.any(~np.isnan(data)):
            times_idx = np.arange(start, stop, 1, dtype=int)
            update_time_range(nc, ncvar, data, times_idx, dry_run, [key])
            return True # should break loop
        return False # continue loop

    # Search start
    for i in range(0, ncvar.size, CHUNK_SIZE) :
        if process_chunk(i, i+CHUNK_SIZE, FIRST_DATA_ATT) :
            break

    # Search end
    for i in range(ncvar.size, 0, -CHUNK_SIZE) :
        if process_chunk(i-CHUNK_SIZE, i, LAST_DATA_ATT):
            break

def update_meta(file, network, dry_run=False, delete=False, update_time=False) :

    mode = "r" if dry_run else "a"
    ncfile = Dataset(file, mode=mode)

    station_id = readShortname(ncfile)
    properties = getProperties(network, station_id)

    # Attribute with null values are ignored : previous value is kept
    properties["FirstData"] = None
    properties["LastData"] = None
    properties["UpdateTime"] = None
    properties["CreationTime"] = None

    handler = HANDLERS[network](properties)

    init_nc(ncfile, properties, handler.data_vars(), dry_run, delete)

    if update_time :
        for varname in handler.data_vars() :
            update_times(ncfile, ncfile.variables[varname], dry_run)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Update meta attributes in NetCDF file')
    parser.add_argument('network', metavar='<NETWORK>', type=str, help='Network')
    parser.add_argument('files', metavar='<file.nc>', type=str, nargs='+', help='NetCDF files to update')
    parser.add_argument('--dry-run', '-n', help='Do not update anything. Just look what would be done', action='store_true', default=False)
    parser.add_argument('--update-times', '-t', help='Update data time ranges for each variable', action='store_true', default=False)
    parser.add_argument('--delete', '-d', help='Delete extra attributes', action='store_true', default=False)
    args = parser.parse_args()

    for file in args.files :
        update_meta(file, args.network, args.dry_run, args.delete, args.update_times)
