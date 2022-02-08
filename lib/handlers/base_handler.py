import os.path
from abc import abstractmethod
from gzip import GzipFile
from io import TextIOWrapper
from typing import final
from zipfile import ZipFile
from pandas import DataFrame
from datetime import datetime
import re


from lib.log import warning, debug


class InSituHandler :
    """ Virtual class to be implemented for each new network """
    
    
    def __init__(self, properties):
        self.properties = properties

    @final
    def read_chunk(self, filename:str, encoding='latin1'):
        """ Handle opening of gz / zip files """

        if filename.endswith(".gz") :
            with open(filename, "rb") as f:
                stream =  TextIOWrapper(GzipFile(fileobj=f), encoding=encoding)
                return self._read_chunk(stream)

        elif filename.endswith('.zip'):  # check if file is a zipped (.zip) file

            with ZipFile(filename) as thezip :
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
        {PropertyName} : Any property defined in station-info csv file

        The pattern is used to sort file by year and month.
        If not provided, the year and month of the modification of the file are used.

        Example patterns :
        - "{ID}-{YY}-{MM}*.zip"
        - "???{ID}*.txt"
        """
        pass

    def glob_pattern(self) :
        """Transforms the pattern to a glob pattern"""
        def subf(match) :
            key = match.group(0)
            if key in ["YY", "MM", "YYYY"] :
                return "?" * len(key)
            else :
                return '*'

        return re.sub(r'\{\w+\}', subf, self.pattern())



    def sort_files(self, filenames, properties):

        properties = properties.copy()

        # Transform pattern to regexp
        def subf(match):
            key = match.group(1)
            if key in ["M", "MM", "YY", "YYYY"] :
                pattern = r'\d+' if key == "M" else r'\d' * len(key)
                return r'(?P<%s>%s)' % (key,pattern)
            else :
                if key in properties :
                    return str(properties[key])
                else:
                    raise Exception("Key '%s' in file pattern '%s' not found in station info" % (key, self.pattern()))

        # Transforms pattern to regular expression for matching
        re_pattern = self.pattern().replace("?", ".").replace("*", ".*")
        re_pattern = re.sub(r'\{(\w+)\}', subf, re_pattern)


        debug(re_pattern=re_pattern)

        def sort_key(filename) :
            basename = os.path.basename(filename)
            match = re.match(re_pattern, basename, flags=re.IGNORECASE)
            if not match :
                warning("File %s does not match pattern %s. Skipping" % (basename, self.pattern()))
                return None

            # By default, use year and month of modification time
            mtime = datetime.fromtimestamp(os.path.getmtime(filename))
            year = mtime.year
            month = mtime.month

            groups = match.groupdict()

            if "M" in groups :
                month = int(groups["M"])
            if "MM" in groups:
                month = int(groups["MM"])
            if "YYYY" in groups :
                year = int(groups["YYYY"])
            if "YY" in groups :
                year = int(groups["YY"])
                year = year + (2000 if year < 70 else 1900)

            return (year, month, basename)

        filenames_keys = dict()
        for filename in filenames :
            key = sort_key(filename)
            if key is not None :
                filenames_keys[filename] = key

        debug(filenames_keys)

        return sorted(list(filenames_keys.keys()), key=lambda filename : filenames_keys[filename])






    @abstractmethod
    def _read_chunk(self, stream) -> DataFrame:
        """
        Should return a panda DataFrame, with a datetime index and columns correponding to #DATA_VARIABLES, as defined in common.py.
        Missing values should be np.nan
        """
        pass

