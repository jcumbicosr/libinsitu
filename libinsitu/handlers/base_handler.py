import os.path
import re
from abc import abstractmethod
from datetime import datetime
from glob import glob
from gzip import GzipFile
from io import TextIOWrapper
from pathlib import PurePath
from typing import Dict
from zipfile import ZipFile

from pandas import DataFrame

from libinsitu import match_pattern
from libinsitu.log import warning, debug

ZERO_DEG_K = 273.15

def map_cols(data, mapping) :
    """Filter and rename columns """
    data = data[list(mapping.keys())]
    return data.rename(columns=mapping)

class InSituHandler :
    """ Virtual class to be implemented for each new network """
    
    def __init__(self, properties):
        self.properties = properties.copy()

        # Also adds lower case version of properties
        for key, val in properties.items() :
            if isinstance(val, str) :
                self.properties[key.lower()] = val.lower()


    # final
    def read_chunk(self, filename:str, encoding='latin1'):
        """ Handle opening of gz / zip files. Filename can contain a zip entry name after '!' """

        zip_entry= None
        if '!' in filename :
            filename, zip_entry = filename.split('!')

        if filename.endswith(".gz") :
            with open(filename, "rb") as f:
                stream =  TextIOWrapper(GzipFile(fileobj=f), encoding=encoding)
                return self._read_chunk(stream)

        elif filename.endswith('.zip'):  # check if file is a zipped (.zip) file

            with ZipFile(filename) as thezip :

                names = thezip.namelist()

                if len(names) == 1 :
                    entry = names[0]
                elif zip_entry is not None: # Explicit zip entry request after !
                    if not zip_entry in names :
                        raise Exception("Missing zip entry '%s' in '%s'" % (zip_entry, filename))
                    entry = zip_entry
                else:
                    # TODO : This was a default harcoded : should be better to set it in each subclass
                    entry = [tmp for tmp in thezip.namelist() if '.txt' in tmp][0]

                stream = thezip.open(entry, mode="r")
                return self._read_chunk(stream)

        else :
            with open(filename, "rt", encoding=encoding) as f :
                return self._read_chunk(f)

    @abstractmethod
    def pattern(self):
        """Should return a file pattern for input files.

        The following placeholders are supported :
        *: any string
        ?: any single caracter
        {MM} : Month of chunk file
        {YYYY} / {YY} : Year of chunk file
        {DDD} : Day of year (1-365)
        {Property_Name} : Any property defined in station-info csv file
        {property_name} : Same property, in lower case

        The pattern is used to sort file by year and month.
        If not provided, the year and month of the modification of the file are used.

        Example patterns :
        - "{Station_ID}-{YY}-{MM}*.zip"
        - "???{ID}*.txt"
        """

        # Take this from the RawDataPath property of the network
        return self.properties["Network_RawDataPath"]

    def glob_pattern(self) :
        """Transforms the pattern to a glob pattern"""
        def subf(match) :
            key = match.group(0).replace("{", "").replace("}", "")
            if key in self.properties:
                return str(self.properties[key])
            elif key in ["YY", "M", "MM", "YYYY", "DDD"] :
                return "?" * len(key)
            else :
                raise Exception("Unsupported pattern : %s" % key)

        return re.sub(r'\{\w+\}', subf, self.pattern())



    def list_files(self, folder):
        """List files from folder matching the pattern """

        # First go a glob
        pattern = folder + "/" + self.glob_pattern()

        debug("Pattern :", pattern)

        filenames = list(_zip_glob(pattern))

        debug("Candidate filenames :", filenames)

        # Finer filter on each name
        def filter_f(filename) :
            basename = os.path.basename(filename)
            return self.match_pattern(basename) is not False

        res =  list(filename for filename in filenames if filter_f(filename))

        debug("Filtered filenames :", res)

        return res

    def match_pattern(self, value):
        pattern = os.path.basename(self.pattern())
        return match_pattern(pattern, value, self.properties)

    def sort_files(self, filenames):

        def sort_key(filename) :
            basename = os.path.basename(filename)

            match_groups = self.match_pattern(basename)
            if not match_groups :
                warning("File %s does not match pattern %s. It may not not be included in correct order" % (basename, self.pattern()))
                return basename

            # By default, use year and month of modification time
            realfilename = filename
            if '!' in filename :
                realfilename, zip_entry = filename.split("!")
            mtime = datetime.fromtimestamp(os.path.getmtime(realfilename))
            year = mtime.year
            month_or_days = mtime.month


            if "M" in match_groups :
                month_or_days = int(match_groups["M"])
            if "MM" in match_groups:
                month_or_days = int(match_groups["MM"])
            if "DDD" in match_groups:
                month_or_days = int(match_groups["DDD"])
            if "YYYY" in match_groups :
                year = int(match_groups["YYYY"])
            if "YY" in match_groups :
                year = int(match_groups["YY"])
                year = year + (2000 if year < 70 else 1900)

            return (year, month_or_days, basename)

        filenames_keys = { filename: sort_key(filename) for filename in filenames}

        return sorted(list(filenames_keys.keys()), key=lambda filename : filenames_keys[filename])


    def data_vars(self):
        # By default, return the list of available data from the CSV files
        return self.properties["Network_AvailableData"].split(",")

    @abstractmethod
    def _read_chunk(self, stream) -> DataFrame:
        """
        Should return a panda DataFrame, with a datetime index and columns correponding to #DATA_VARIABLES, as defined in common.py.
        Missing values should be np.nan
        """
        pass

def _zip_entries(zip_file) :
    with ZipFile(zip_file) as thezip:
        return thezip.namelist()

def _zip_glob(pattern) :
    """Extension of 'glob' that supports looking into ZIP file entries (after '!')"""
    entries_pattern = None
    if '!' in pattern :
        pattern, entries_pattern = pattern.split("!")

    files = glob(pattern)
    if entries_pattern is None :
        return files

    res = []
    for zipfile in files :
        for entry in  _zip_entries(zipfile) :
            if PurePath(entry).match(entries_pattern) :
                res.append(zipfile + '!' + entry)
    return res

