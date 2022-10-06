# Data & networks


## Thredds server

We publish the resulting NetCDF files on a [thredds data server](http://tds.webservice-energy.org/thredds/catalog.html).
We currently only provide open access to the networks explicitly allowing data redistribution in their licence :

```{csv-table}
---
header-rows: 1
file: networks.csv
---
```

## Web interface

We also provide [a web interface](http://viewer.webservice-energy.org/in-situ/) on top of this thredds server.
It provides :
* A map of available stations
* Visualization if time series
* Export to CSV or JSON 
* A view of visual quality graphs
* An overview of the time range of each station

```{image} _static/img/web-interface.png
---
target: http://viewer.webservice-energy.org/in-situ/
alt: Preview of web interface
---
```