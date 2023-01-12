1.3 :
* Fixed bug splitting meta data with "," to lists
* Added CLI utils ins-update-meta, to only update metadata for NetCDF files without recomputing data
* Refactor of QC flags
* Fixed CDL to be better compliant with cf conventions

1.2 :
* Fixed bug in date filtering of nc2df with start date different from origin date
* Migrated to new conventions
* Added QC flags and ins-qc (cli) to generate visual QC images and add flags in NetCDF files
* Added handler for IEA_PVPS, ESMAP, SKYNET, ISE_PVLIVE
* Added CLI ins-info to dump CSV meta data
* Added stats and header to cat.py (formely dump.py)

1.1 :
* Separate start date from date-origin
* Set date origin to a fixed value : 1970-01-01 UTC

1.0 :
* First release on PyPI