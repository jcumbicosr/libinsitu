import zipfile
from abc import abstractmethod
from gzip import GzipFile
from io import TextIOWrapper
from typing import final
from zipfile import ZipFile

from pandas import DataFrame


class InSituHandler :
    """ Virtual class to be implemented for each new network """

    @final
    def read_chunk(self, filename:str, encoding='latin1'):
        """ Handle opening of gz / zip files """

        if filename.endswith("gz") :
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
        """Should return a file pattern like : *.txt """
        pass

    @abstractmethod
    def _read_chunk(self, stream) -> DataFrame:
        """
        Should return a panda DataFrame, with a datetime index and columns correponding to #DATA_VARIABLES, as defined in common.py.
        Missing values should be np.nan
        """
        pass

