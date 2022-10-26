#!/usr/bin/env python
from libinsitu.handlers import HANDLERS
from libinsitu.common import *
from libinsitu.cdl import init_nc
from libinsitu.log import *
import argparse


def update_times(outds, start_date64, dry_run=False) :
    time_var = getTimeVar(outds)
    resolution_s = getTimeResolution(outds)
    start_sec = datetime64_to_sec(outds, start_date64)

    if time_var[0] != start_sec :
        if dry_run :
            info("Would have updated times values. Firs value : %d => %d" % (time_var[0], start_sec))
        else:
            info("Updating time values. Firs value : %d => %d" % (time_var[0], start_sec))
            time_values = np.arange(start_sec, start_sec + resolution_s * len(time_var), resolution_s)
            time_var[:] = time_values
    else:
        info("First time value was corect : no update required")


def update_meta(input, output, network=None, dry_run=False, delete=False, update_time=False) :

    if output is None :
        output = input

    # Output
    new = not os.path.exists(output)

    if dry_run :
        mode= 'r'
    elif new :
        mode = "w"
    else:
        mode = "a"

    outds = Dataset(output, mode=mode)

    # Input
    if input == output :
        inds = outds
    else:
        inds = Dataset(input, mode="r")

    # Guess network
    if network is None :
        network = getattr(inds, "network_id", None)
        if network is None :
            raise Exception("Unable to guess network name. Please provide it")


    station_id = read_str(inds.variables[STATION_NAME_VAR])
    properties = getProperties(network, station_id)

    timeVar = getTimeVar(inds)
    first_time = sec_to_datetime64(inds, timeVar[0]).data[()]
    last_time = sec_to_datetime64(inds, timeVar[-1]).data[()]

    # Attribute with null values are ignored : previous value is kept
    properties["FirstData"] = time2str(first_time, seconds=True)
    properties["LastData"] = time2str(last_time, seconds=True)
    properties["UpdateTime"] = None
    properties["CreationTime"] = None

    handler = HANDLERS[network](properties)

    init_nc(outds, properties, handler.data_vars(), dry_run, delete)

    if inds != outds :

        # copy all file data except for the excluded
        for vname, variable in inds.variables.items():
            if vname in outds.variables and "time" in variable.dimensions :
                info("Copying data of var '%s' from '%s' to '%s'" % (vname, input, output))

                outds.variables[vname][:] = variable[:]

    if update_time :
        start_date = str_to_date64(properties["Station_StartDate"])
        update_times(outds, start_date, dry_run)

def main() :

    parser = argparse.ArgumentParser(description='Update meta attributes in NetCDF file')
    parser.add_argument('input', metavar='<input.nc>', type=str, help='NetCDF file to update')
    parser.add_argument('--output', '-o', metavar='<output.nc>', type=str, help='NetCDF files to update', default=None)
    parser.add_argument('--network', metavar='<network_id>', type=str, help='Network. Guessed from reading the file if not provided')
    parser.add_argument('--dry-run', '-n', help='Do not update anything. Just look what would be done', action='store_true', default=False)
    parser.add_argument('--update-ranges', '-ur', help='Update data time ranges for each variable', action='store_true', default=False)
    parser.add_argument('--delete', '-d', help='Delete extra attributes', action='store_true', default=False)
    args = parser.parse_args()

    update_meta(args.input, args.output, args.network, args.dry_run, args.delete, args.update_ranges)

if __name__ == '__main__':
    main()
