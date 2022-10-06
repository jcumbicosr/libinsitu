# Introduction

**libinsitu** is a library to transform solar in situ data into a standard *NetCDF* format.

The aim is to improve **standardization** and **interoperability**, to leverage development of new tools.  

It provides :
* A set of [CLI utilities](cli/index.md) and [Python functions](api.md) to :
  * Transform **raw input files** into **NetCDF** format
  * **Explore & query** NetCDF files, and transform it to various formats (*CSV*, *JSON*, *text*, *pandas Dataframes*)
  * Flag data with **quality checks** and produce graphs for **visual quality control**
* A set of {gitref}`formatted and enriched metadata<libinsitu/res/station-info>` for several networks and their stations.
* A [proposed convention](conventions.md) for solar data, on top of CF conventions.

In addition, we process input data for many networks and [make them available](data) 
through a [Thredds data server](http://tds.webservice-energy.org/thredds/catalog.html) and 
a [web interface](http://viewer.webservice-energy.org/in-situ/). For more details, see the [data](data) section.

```{image} _static/img/web-interface.png
---
target: http://viewer.webservice-energy.org/in-situ/
alt: Preview of web interface
---
```


## Installation

libinsitu is available via *pip* :
```bash
pip install libinsitu
```

## Authors

*libinsitu* is developped and maintained by Raphaël Jolivet and Yves Marie Saint-Drenan, 
from the research center [O.I.E of Mines-Paristech](https://www.oie.minesparis.psl.eu/Accueil/) 

## Contact and discussion 

Please subscribe to the mailing list :<br/>
[solar-insitu@groupes.mines-paristech.fr](https://groupes.minesparis.psl.eu/wws/info/solar-insitu)

## Licence

*libinsitu* is distributed under the {gitref}`BSD 2-Clause License <LICENSE>`

## Source code

The source code is available of our {gitref}`gitlab </>`


## Summary 

```{toctree}
---
maxdepth: 2
---
Introduction <self>
api
cli/index
data
conventions
```