import os
import tempfile
from unittest.mock import patch

from pandas import DataFrame
from datetime import datetime

def tmp_filename(name='tmpfile') :
    return os.path.join(tempfile.mkdtemp(), name)

def mk_timeseries(**dic):
    """Creates a time series Dataframe from a dict of values """
    nb = len(list(dic.values())[0])

    # Expand single value
    for name, vals in dic.items() :
        if not isinstance(vals, list) :
            dic[name] = [vals] * nb

    dic["times"] = [datetime(2000, 1, 1, 0, min, 0) for min in range(0, nb)]
    df = DataFrame.from_dict(dic)
    return df.set_index("times")

def patch_flags(flags) :

    flags = {flag.name : flag for flag in flags}
    return patch("libinsitu.qc.qc_utils.get_flags", return_value=flags)