from libinsitu.common import netcdf_to_dataframe, get_periods
from libinsitu.log import *
import numpy as np

def check_time(filename) :

    df = netcdf_to_dataframe(filename)
    station_id = df.attrs["StationInfo_Abbreviation"]
    network = df.attrs["source"]
    if " " in network :
        network = network.split(" ")[0]

    with LogContext(station_id=station_id, network=network, file=filename) :

        from_date = min(df.index)
        to_date = max(df.index)
        nb_samples = len(df.index)

        time_s = df.index.values.astype(np.int64) // 1000000000

        periods = get_periods(time_s)

        if len(periods) > 1 :
            warning("Found several periods periods=%s", periods)
        else:
            periods = list(periods.keys())[0]
        info("from:%s, to:%s, %d samples, period:%s", from_date, to_date, nb_samples, periods)

def main() :
    """Perform various checks on a InSitu NetCDF file"""
    for file in sys.argv[1:] :
        with IgnoreAndLogExceptions() :
            check_time(filename=file)

if __name__ == '__main__':
    main()
