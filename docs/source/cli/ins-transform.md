# ins-transform

```{argparse}
---
module: libinsitu.cli.transform
func: parser
prog: ins-transform
---
```

## Converting custom Excel or CSV files

By default, *libinsitu* embeds decoders for {gitref}`several networks <libinsitu/handlers>`

To convert your own custom files, you need :
* A **schema CDL file**, describing the layout of the output NetCDF file and the variables it contains. 
  By default, the {gitref}`embedded CDL <libinsitu/res/base.cdl>` is used.  
* A CSV file containing the metadata for each station, similar to the {gitref}`embedded ones <libinsitu/res/station-info>`.
* A `mapping.json` file, describing the mapping between the columns of the input files, and the variables of the output NetCDF file.

### Example call 



The following command encodes all `zip` files of the folder `in/ABOM/LER` into the netcdf file `ABOM-LER.nc`. 

```sh 
ins-transform --network ABOM --station-id LER ABOM-LER.nc in/ABOM/LER/*.zip
```