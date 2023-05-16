import os
import pandas as pd

from functools import wraps
from typing import Any

from vantage6.client.algorithm_client import AlgorithmClient
from vantage6.tools.wrappers import (
    CSVWrapper, ExcelWrapper, SparqlDockerWrapper, ParquetWrapper,
    SQLWrapper, OMOPWrapper
)
from vantage6.tools.wrap import load_input
from vantage6.tools.util import info, error, warn


def algorithm_client(func: callable) -> callable:
    """
    Decorator that adds an algorithm client object to a function

    By adding @algorithm_client to a function, the ``algorithm_client``
    argument will be added to the front of the argument list. This client can
    be used to communicate with the server.

    Parameters
    ----------
    func : callable
        Function to decorate

    Returns
    -------
    callable
        Decorated function
    """
    def wrap_function(*args, **kwargs):
        # read server address from the environment
        host = os.environ["HOST"]
        port = os.environ["PORT"]
        api_path = os.environ["API_PATH"]

        # read token from the environment
        token_file = os.environ["TOKEN_FILE"]
        info("Reading token")
        with open(token_file) as fp:
            token = fp.read().strip()

        client = AlgorithmClient(token=token, host=host, port=port,
                                 path=api_path)
        return func(client, *args, **kwargs)
    return wrap_function


def data(number_of_databases: int = 1) -> callable:
    """
    Decorator that adds algorithm data to a function

    By adding @data to a function, one or several pandas dataframes will be
    added to the front of the argument list. This data will be read from the
    databases that the user who creates the task provides.

    Note that the user should provide exactly as many databases as the
    decorated function requires when they create the task.

    Parameters
    ----------
    num: int
        Number of data sources to load. These will be loaded in order by which
        the user provided them. Default is 1.

    Returns
    -------
    callable
        Decorated function

    Examples
    --------
    >>> @data(num=2)
    >>> def my_algorithm(first_df: pd.DataFrame, second_df: pd.DataFrame,
    >>>                  <other arguments>):
    >>>     pass
    """
    def protection_decorator(func: callable, *args, **kwargs) -> callable:
        @wraps(func)
        def decorator(*args, **kwargs) -> callable:
            # query to execute on the database
            input_file = os.environ["INPUT_FILE"]
            info(f"Reading input file {input_file}")
            input_data = load_input(input_file)

            # read the labels that the user requested, which is a comma
            # separated list of labels.
            labels = os.environ["USER_REQUESTED_DATABASE_LABELS"]
            labels = labels.split(',')

            # check if user provided enough databases
            if len(labels) < number_of_databases:
                error(f"User provided {len(labels)} databases, but algorithm "
                      f"requires {number_of_databases} databases. Exiting...")
                exit(1)
            elif len(labels) > number_of_databases:
                warn(f"User provided {len(labels)} databases, but algorithm "
                     f"requires {number_of_databases} databases. Using the "
                     f"first {number_of_databases} databases.")

            for i in range(number_of_databases):
                label = labels[i]
                data_ = _get_data_from_label(label, input_data)
                args = (data_, *args)

            return func(*args, **kwargs)
        return decorator
    return protection_decorator


def _get_data_from_label(label: str, input_data: Any) -> pd.DataFrame:
    """
    Load data from a database based on the label

    Parameters
    ----------
    label : str
        Label of the database to load
    input_data : Any
        Input data from the input file

    Returns
    -------
    pd.DataFrame
        Data from the database
    """
    # Load the input data from the input file - this may e.g. include the
    database_uri = os.environ[f"{label.upper()}_DATABASE_URI"]
    info(f"Using '{database_uri}' with label '{label}' as database")

    # Get the database type from the environment variable, this variable is
    # set by the vantage6 node based on its configuration file.
    database_type = os.environ.get(
        f"{label.upper()}_DATABASE_TYPE", "csv").lower()

    # Create the correct wrapper based on the database type, note that the
    # multi database wrapper is not available.
    if database_type == "csv":
        wrapper = CSVWrapper()
    elif database_type == "excel":
        wrapper = ExcelWrapper()
    elif database_type == "sparql":
        wrapper = SparqlDockerWrapper()
    elif database_type == "parquet":
        wrapper = ParquetWrapper()
    elif database_type == "sql":
        wrapper = SQLWrapper()
    elif database_type == "omop":
        wrapper = OMOPWrapper()
    else:
        error(f"Unknown database type '{database_type}' for database with "
              f"label '{label}'. Please check the node configuration.")
        exit(1)

    # Load the data from the database
    return wrapper.load_data(database_uri, input_data)
