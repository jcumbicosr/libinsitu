#!/usr/bin/env python
from libinsitu.handlers import HANDLERS
from libinsitu.common import *
from libinsitu.cdl import init_nc
from libinsitu.log import *
import argparse

def update_times(nc, ncvar, dry_run=False) :

    dry_prefix = "would " if dry_run else ""

    def process_chunk(start, stop, key) :
        data = ncvar[start:stop]
        if np.any(~np.isnan(data)):
            times_idx = np.arange(start, stop, 1, dtype=int)
            time_limit = getMinMaxTimes(nc, data, times_idx, ncvar.name)[key]

            if time_limit is not None :
                new_val = time2str(time_limit)
                old_val = None if not key in ncvar.ncattrs() else ncvar.getncattr(key)
                if old_val != new_val:
                    info(dry_prefix + "update %s:%s %s -> %s" % (ncvar.name, key, old_val, new_val))
                if not dry_run:
                    ncvar.setncattr(key, time2str(time_limit))
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


def main() :

    parser = argparse.ArgumentParser(description='Update meta attributes in NetCDF file')
    parser.add_argument('network', metavar='<NETWORK>', type=str, help='Network')
    parser.add_argument('files', metavar='<file.nc>', type=str, nargs='+', help='NetCDF files to update')
    parser.add_argument('--dry-run', '-n', help='Do not update anything. Just look what would be done', action='store_true', default=False)
    parser.add_argument('--update-times', '-t', help='Update data time ranges for each variable', action='store_true', default=False)
    parser.add_argument('--delete', '-d', help='Delete extra attributes', action='store_true', default=False)
    args = parser.parse_args()

    for file in args.files :
        update_meta(file, args.network, args.dry_run, args.delete, args.update_times)

if __name__ == '__main__':
    main()
