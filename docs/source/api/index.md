# Python API

The usage of Python API is demonstrated in [several Notebooks](https://git.sophia.mines-paristech.fr/oie/libinsitu/-/tree/main/notebooks)

* [netcdf_to_dataframe](netcdf_to_dataframe) : Read a NetCDF file (or OpenDAP URL) into a pandas dataframe
* [dataframe_to_netcdf](dataframe_to_netcdf) : Encodes a pandas Dataframe into a NetCDF file
* [compute_qc_flags](compute_qc_flags) : Compute QC flags of a Dataframe of irradiance
* [visual_qc](visual_qc) : Generates visual QC from a dataframe


```{toctree}
---
hidden:
maxdepth: 1
---
netcdf_to_dataframe
dataframe_to_netcdf
compute_qc_flags
visual_qc
```