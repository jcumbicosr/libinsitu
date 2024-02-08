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
* A `mapping.json` (or yaml) file, describing the mapping between the columns of the input files, and the variables of the output NetCDF file.

### Format of the mapping file

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
        "dest_var2" : { # Expanded mapping for var 
            "col" : "source_col", # Name of source column
            "scale" : 100, # [Optional] Scale to apply to source data. 1 by default (no scale)           
            "offset" : 12.1, # [Optional] Offset to apply to source data. 0 by default. Offset is applied after scale. 
        }
    }
}
```

### Examples of transforming custom files

Here is an example for transforming custom *csv* file into NetCDF : 

```shell
ins-transform \
--no-qc \
--station-metadata stations.csv \
--cdl schema.cdl \ 
--mapping mapping.yaml \
--station-id AAA \
AAA.nc input.csv
```

This command will create the file `AAA.nc`. If the file already exists, it will be updated. 

The input files look like this:

**mapping.yaml**
```yaml 
mapping:
  time:
    col: [Date, Time]
    format: "%Y-%m-%d %H:%M"
    timezone: "-01:00"
  temperature: Temp
separator: ";"
```

**input.csv**

| Date       | Time  | Temp |
|------------|-------|------|
| 2008-08-01 | 00:05 | 10.5 |
| 2008-08-01 | 00:10 | 12   |
| 2008-08-01 | 00:15 | 13   |
| 2008-08-01 | 00:20 | 14   |


**stations.csv**

| Name        | ID  | Latitude | Longitude | Elevation | TimeResolution | StartDate  |
|-------------|-----|----------|-----------|-----------|----------------|------------|
| Station AAA | AAA | 9.0667   | 7.4833    | 536       | 5M             | 2008-07-30 |

**schema.cdl**

This custom schema defines the list of variables and metadata, follwing **CF conventions**, 
with placeholders replaced by values of the file `stations.csv`.  

```
netcdf base {

dimensions:
  time = UNLIMITED ; # Main dimension

variables:

    # Dummy var, holding CRS data for GIS software
    double crs;
        *:grid_mapping_name = "latitude_longitude" ;
        *:longitude_of_prime_meridian = 0.0 ;
        *:semi_major_axis = 6378137.0 ;
        *:inverse_flattening = 298.257223563 ;
        *:epsg_code = "EPSG:4326";
        *:_FillValue = -999.0;

    # Static scalar value, filled from meta data
    string station_name;
        *:standard_name = "platform_name" 
        *:long_name = "station_name" ;
        *:cf_role = "timeseries_id" ;
        *:_value = {!Station_ID}; 

    # Single scalar value, filled from meta data
    float latitude;
        *:long_name = "station latitude" ;
        *:standard_name = "latitude" ;
        *:units = "degrees_north" ;
        *:_CoordinateAxisType = "Lat" ;
        *:_value = {!Station_Latitude};
        *:axis = "Y" ;

    # Single scalar value, filled from meta data
    float longitude;
        *:long_name = "station longitude" ;
        *:standard_name = "longitude" ;
        *:units = "degrees_east" ;
        *:_CoordinateAxisType = "Lon" ;
        *:_value = {!Station_Longitude};
        *:axis = "X" ;

    # Single scalar value, filled from meta data
    float elevation;
        *:long_name = "Elevation above mean seal level" ;
        *:standard_name = "height_above_mean_sea_level" ;
        *:_CoordinateAxisType = "Z" ;
        *:units = "m" ;
        *:_value = {!Station_Elevation};
        *:axis = "Z" ;

    # Time : UTC, uniform, expressed as seconds since epoch.
    uint time(time) ;
        *:long_name = "Time of measurement" ;
        *:standard_name = "time" ;
        *:units = "seconds since 1970-01-01 00:00:00";
        *:time_origin = "1970-01-01 00:00:00" ;
        *:time_zone= "UTC"
        *:_CoordinateAxisType = "Time" ;
        *:axis = "T" ;
        *:calendar = "gregorian" ;

    # Single data var
    float temperature(time) ;
        *:long_name = "Air temperature at 2 m height" ;
        *:standard_name = "air_temperature" ;
        *:coordinates = "time latitude longitude elevation "
        *:units = "K";
        *:grid_mapping = "crs" ;
        *:least_significant_digit=1; # Excepted precision, for losly compression 
        *:_FillValue = -999.0;

# Global attributes

  # Main info
  :id = "{Network_ID}-{Station_ID}";
  :title = "Timeseries of {Network_ID}. Station : {Station_Name}" ;
  :keywords_vocabulary = "GCMD Science Keywords" ;
  :keywords_vocabulary_url = "https://gcmd.earthdata.nasa.gov/static/kms/" ;
  :record = "Basic measurements (global irradiance, direct irradiance, diffuse irradiance, air temperature, relative humidity, pressure)" ;
  :featureType = "timeSeries" ;
  :cdm_data_type = "timeSeries";
  :product_version = "libinsitu {Version}"
  
  # Conventions
  :Conventions = "CF-1.10 ACDD-1.3";
  
  # Publisher [ACDD1.3]
  :publisher_name = "Name of publisher of data";
  :publisher_email = "publisher@email.com";
  :publisher_url = "http://publisher.url" ;
  :publisher_institution = "Publisher institution name"
  
  # Creator info [ACDD1.3]
  :creator_name =  "Creator of data" ;
  :institution =  "{Station_Institute}" ;
  :metadata_link =  "{Station_Url}";
  :creator_email = "{Network_Email}";
  :creator_url = "{Network_URL}" ;
  :references = "http://some.doi" ;
  :license = "{Network_License}" ;
  :comment = "{Station_Comment}" ;
  
  # Station info & coordinates [ACDD1.3]
  :project = "Network name"; # Network long name
  :platform = "{Station_Name}" ; # Should be a long / full name
  :geospatial_lat_min = {Station_Latitude} ;
  :geospatial_lon_min = {Station_Longitude} ;
  :geospatial_lat_max = {Station_Latitude} ;
  :geospatial_lon_max = {Station_Longitude} ;
  :geospatial_vertical_min = {Station_Elevation};
  :geospatial_vertical_max = {Station_Elevation};
  :geospatial_bounds = "POINT({Station_Latitude} {Station_Longitude})";
  :geospatial_bounds_crs = "EPSG:4326";
  
  # Time information
  :time_coverage_start = "{Station_StartDate}T00:00:00" ;  # First data [Dataset Discovery v1.0]
  :time_coverage_end = "{LastData}";  # Last data [Dataset Discovery v1.0]
  :time_coverage_resolution = "P{Station_TimeResolution}"; # Resolution in  ISO 8601:2004 duration format [Dataset Discovery v1.0]
  :local_time_zone = "{Station_Timezone}" ;
  :date_created = "{CreationTime}";
  :date_modified = "{UpdateTime}";

}
```

The resulting `NetCdf` file should contain all data and metadata.

Here is the output of `ins-cat -t CSV -hd AAA.nc`, dumping NetCDF data and metadata as a CSV file:

```
# id = MyNetwork-AAA
# title = Timeseries of . Station : Station AAA
# keywords_vocabulary = GCMD Science Keywords
# keywords_vocabulary_url = https://gcmd.earthdata.nasa.gov/static/kms/
# record = Basic measurements (global irradiance, direct irradiance, diffuse irradiance, air temperature, relative humidity, pressure)
# featureType = timeSeries
# cdm_data_type = timeSeries
# product_version = libinsitu unset (local)
# Conventions = CF-1.10 ACDD-1.3
# publisher_name = Name of publisher of data
# publisher_email = publisher@email.com
# publisher_url = http://publisher.url
# publisher_institution = Publisher institution name
# creator_name = Creator of data
# references = http://some.doi
# project = Network name
# platform = Station AAA
# geospatial_lat_min = 9.0667
# geospatial_lon_min = 7.4833
# geospatial_lat_max = 9.0667
# geospatial_lon_max = 7.4833
# geospatial_vertical_min = 536
# geospatial_vertical_max = 536
# geospatial_bounds = POINT(9.0667 7.4833)
# geospatial_bounds_crs = EPSG:4326
# time_coverage_start = 2008-07-30T00:00:00
# time_coverage_resolution = 300
# date_created = 2023-11-28T17:46:03.687062
# date_modified = 2023-11-28T17:46:03.687062
# latitude = 9.0667
# longitude = 7.4833
# elevation = 536.0
# station_name = AAA
# variables:
#   crs:
#     _FillValue = -999.0
#     grid_mapping_name = latitude_longitude
#     longitude_of_prime_meridian = 0.0
#     semi_major_axis = 6378137.0
#     inverse_flattening = 298.257223563
#     epsg_code = EPSG:4326
#   station_name:
#     standard_name = platform_name
#     long_name = station_name
#     cf_role = timeseries_id
#   latitude:
#     long_name = station latitude
#     standard_name = latitude
#     units = degrees_north
#     _CoordinateAxisType = Lat
#     axis = Y
#   longitude:
#     long_name = station longitude
#     standard_name = longitude
#     units = degrees_east
#     _CoordinateAxisType = Lon
#     axis = X
#   elevation:
#     long_name = Elevation above mean seal level
#     standard_name = height_above_mean_sea_level
#     _CoordinateAxisType = Z
#     units = m
#     axis = Z
#   time:
#     long_name = Time of measurement
#     standard_name = time
#     units = seconds since 1970-01-01 00:00:00
#     time_origin = 1970-01-01 00:00:00
#     time_zone = UTC
#     abbreviation = Date/Time
#     _CoordinateAxisType = Time
#     axis = T
#     calendar = gregorian
#   temperature:
#     _FillValue = -999.0
#     least_significant_digit = 1
#     long_name = Air temperature at 2 m height
#     standard_name = air_temperature
#     coordinates = time latitude longitude elevation
#     abbreviation = T2
#     units = K
#     grid_mapping = crs
time,temperature
2008-08-01 01:05:00,10.5
2008-08-01 01:10:00,12.0
2008-08-01 01:15:00,13.0
2008-08-01 01:20:00,14.0
```





