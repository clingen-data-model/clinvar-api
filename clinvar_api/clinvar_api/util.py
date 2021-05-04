import os
import pandas
import numpy

def str_to_bool(s):
    """
    Returns false if s is "false", else returns true.
    """
    if s == "false":
        return False
    return True

def makedir_if_not_exists(dirname: str):
    """
    Makes the directory with the path dirname if a directory at that path does not exist.
    Throws exception if a filesystem entry by that name exists but is not a directory.
    """
    if os.path.exists(dirname):
        if os.path.isdir(dirname):
            return
        else:
            raise RuntimeError("Path {} already exists".format(dirname))
    else:
        os.mkdir(dirname)

def pandas_df_without_nan(df: pandas.DataFrame, value:object=None) -> pandas.DataFrame:
    """
    Takes a pandas DataFrame, replaces the numpy.nan values with None.
    Or with value specified with optional `value` kwarg.
    """
    return df.replace({numpy.nan: value})
