# Quality control 

*Libinsitu* embeds several features for QC analysis :

* Computes QC flags and embeds it into NetCDF files : 
  * Via the CLI : command [ins-transform](cli/ins-transform.md)
  * Via the Python API : function [compute_qc_flags](api/compute_qc_flags.md)
 
* Filters out flagged data :
  * Via the CLI : command [ins-cat](cli/ins-cat.md) 
  * Via Python API : parameter `skip_qc` of function [netcdf_to_dataframe](api/netcdf_to_dataframe.md)

## NetCDF encoding

The QC flags are encoded into NetCDF following the CF convention. 
See the [dedicated section in our convention](conventions.md#quality-flags) 

{#qc-flags}
## List of QC Flags

The processed QC flags are controlled by  {gitref}`an embedded declarative CSV file <libinsitu/res/qc-tests.csv>`.

A flag is processed if the variables are included in the `domain`. It passes (value=0 ) if the `condition` matches,  or fails (value=1) otherwize.  

```{csv-table}
---
header-rows: 1
file: ../../libinsitu/res/qc-tests.csv
---
```