# netcdf_to_dataframe

This function takes local or remote (via OpenDAP) NetCDF file and transforms it into a Pandas DataFrame.

```{eval-rst}  
.. autofunction:: libinsitu.netcdf_to_dataframe
```

## Example

```
# Fetch one year of data over the network (OpenDAP), for 3 variables
df = netcdf_to_dataframe(
    "http://tds.webservice-energy.org/thredds/dodsC/nrelmidc-stations/NREL_MIDC-BMS.nc",
    start_time=datetime(2020, 1, 1),
    end_time=datetime(2021, 3, 1),
    vars=["GHI", "BNI", "DHI"])
```