# ins-transform

`ins_transform` enables to parse external files of various formats, and encode them into `NetCDF`. 

```{argparse}
---
module: libinsitu.cli.transform
func: parser
prog: ins-transform
---
```


### Converting supported networks 

The following command encodes all `zip` files of the folder `in/ABOM/LER` into the netcdf file `ABOM-LER.nc`. 

```sh 
ins-transform --network ABOM --station-id LER ABOM-LER.nc in/ABOM/LER/*.zip
```

## Converting custom Excel or CSV files

By default, *libinsitu* embeds decoders for {gitref}`several networks <libinsitu/handlers>`

To convert your own custom files, you need :
* A **schema CDL file**, describing the layout of the output NetCDF file and, its variables and metadata.
  This file may refer placeholders `{Station_XXX}` and `{Network_XXX}`, replaced by the values found in **station** and *network** CSV files.
  By default, the {gitref}`embedded CDL <libinsitu/res/base.cdl>` is used.  
* A *CSV* file containing the metadata for each station, similar to the {gitref}`embedded ones <libinsitu/res/station-info>`.
* Optionally, a CSV files containing network metadata : to replace the placeholders `{Netowrk_XXX}`
* A `mapping.json` file, describing the mapping between the columns of the input files, and the variables of the output NetCDF file.

## Format of mapping file

The mapping file can be either in **JSON** or **YAML**.
It should follow this format :

```python
{
    "separator" : ";",  # [Optional] Separator for CSV files. Default : ","
    "skip_lines": [1, 2, 4], # [Optional ] list of header lines to skip, starting at one. Default : None 
    "mapping" : { # Actual mapping of variables. Keys are destination variables as found in the CDL schema.
        "time" : "timetamp", # Compact format for time mapping, with single column name 
        # -- OR --
        "time" : { # Expanded mapping for time
            "col" : ["date", "time"], # One or more source columns for time
            "format" : "%Y/%m/%d %H:%M:%S", # [Optional] Format of date and time. Infered by default
            "timezone" : "CET", # [Optional] UTC by default. Can be "TimzoneName", or "+0400" or placeholders "{Station_Timezone}"
        },
      
        # -- Data var mapping --
        "dest_var1" : "source_col1", # Compact format for mapping
        
        # -- OR --
        "dest_var2" : {
            "col" : "source_col", # Name of source column
            "scale" : 100, # [Optional] Scale to apply to source data. 1 by default (no scale)           
            "offset" : 12.1, # [Optional] Offset to apply to source data. 0 by default. Offset is applied after scale. 
        }
    }
}
```

### Examples of transforming custom files

Here is a minimalistic example for transforming 
