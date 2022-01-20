from abc import abstractmethod

from pandas import DataFrame


class InSituHandler :
    """ Virtual class to be implemented for each new network """

    @abstractmethod
    def read_chunk(self, filename:str) -> DataFrame:
        """
        Should return a panda DataFrame, with a datetime index and columns correponding to #DATA_VARIABLES, as defined in common.py.
        Missing values should be np.nan
        """
        pass

