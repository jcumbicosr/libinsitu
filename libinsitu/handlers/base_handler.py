import os.path
import re
from abc import abstractmethod
from datetime import datetime
from glob import glob
from gzip import GzipFile
from io import TextIOWrapper
from zipfile import ZipFile

from pandas import DataFrame

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
        """ Handle opening of gz / zip files """

        if filename.endswith(".gz") :
            with open(filename, "rb") as f:
                stream =  TextIOWrapper(GzipFile(fileobj=f), encoding=encoding)
                return self._read_chunk(stream)

        elif filename.endswith('.zip'):  # check if file is a zipped (.zip) file

            with ZipFile(filename) as thezip :
                if len(thezip.namelist()) == 1 :
                    archive = thezip.namelist()[0]
                else:
                    archive = [tmp for tmp in thezip.namelist() if '.txt' in tmp][0]

                stream = thezip.open(archive, mode="r")
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
            if key in ["YY", "M", "MM", "YYYY", "DDD"] :
                return "?" * len(key)
            else :
                return '*'

        return re.sub(r'\{\w+\}', subf, self.pattern())

    def re_pattern(self) :
        """ Transform pattern to regexp matching groups for replacement """
        def subf(match):
            key = match.group(1)
            if key in ["M", "MM", "YY", "YYYY", "DDD"] :
                pattern = r'\d+' if key == "M" else r'\d' * len(key)
                return r'(?P<%s>%s)' % (key,pattern)
            else :
                if key in self.properties :
                    return str(self.properties[key])
                else:
                    raise Exception("Key '%s' in file pattern '%s' not found in station info" % (key, self.pattern()))

        # Transforms pattern to regular expression for matching
        pattern = os.path.basename(self.pattern())
        re_pattern = pattern.replace("?", ".").replace("*", ".*")
        return re.sub(r'\{(\w+)\}', subf, re_pattern)

    def list_files(self, folder):
        """List files from folder matching the pattern """

        # First go a glob
        pattern = folder + "/" + self.glob_pattern()

        debug("Pattern :", pattern)

        filenames = list(glob(pattern))

        debug(pattern, filenames)

        re_pattern = self.re_pattern()

        debug(re_pattern)

        # Finer filter on each name
        def filter_f(filename) :
            basename = os.path.basename(filename)
            return True if re.match(re_pattern, basename, flags=re.IGNORECASE) else False

        return list(filename for filename in filenames if filter_f(filename))

    def sort_files(self, filenames):

        re_pattern = self.re_pattern()

        def sort_key(filename) :
            basename = os.path.basename(filename)
            match = re.match(re_pattern, basename, flags=re.IGNORECASE)
            if not match :
                warning("File %s does not match pattern %s. It may not not be included in correct order" % (basename, self.pattern()))
                return basename

            # By default, use year and month of modification time
            mtime = datetime.fromtimestamp(os.path.getmtime(filename))
            year = mtime.year
            month_or_days = mtime.month

            groups = match.groupdict()

            if "M" in groups :
                month_or_days = int(groups["M"])
            if "MM" in groups:
                month_or_days = int(groups["MM"])
            if "DDD" in groups:
                month_or_days = int(groups["DDD"])
            if "YYYY" in groups :
                year = int(groups["YYYY"])
            if "YY" in groups :
                year = int(groups["YY"])
                year = year + (2000 if year < 70 else 1900)

            return (year, month_or_days, basename)

        filenames_keys = { filename: sort_key(filename) for filename in filenames}

        return sorted(list(filenames_keys.keys()), key=lambda filename : filenames_keys[filename])


    def data_vars(self):
        """Should return the list of data variables supported by the network."""
        raise Exception("Should return the list of supported VARS")

    @abstractmethod
    def _read_chunk(self, stream) -> DataFrame:
        """
        Should return a panda DataFrame, with a datetime index and columns correponding to #DATA_VARIABLES, as defined in common.py.
        Missing values should be np.nan
        """
        pass

