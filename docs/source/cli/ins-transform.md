# ins-transform

```{argparse}
---
module: libinsitu.cli.transform
func: parser
prog: ins-transform
---
```

## Examples

The following command encodes all `zip` files of the folder `in/ABOM/LER` into the netcdf file `ABOM-LER.nc`. 

```sh 
ins-transform --network ABOM --station-id LER ABOM-LER.nc in/ABOM/LER/*.zip
```