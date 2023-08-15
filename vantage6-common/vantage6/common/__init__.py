import os
import base64
import click
import appdirs
import ipaddress
import typing

from colorama import init, Fore, Style

from vantage6.common.globals import APPNAME, STRING_ENCODING


# init colorstuff
init()


def logger_name(special__name__: str):
    """
    Return the name of the logger.

    Parameters
    ----------
    special__name__: str
        The __name__ variable of a module.

    Returns
    -------
    str
        The name of the logger.
    """
    log_name = special__name__.split('.')[-1]
    if len(log_name) > 14:
        log_name = log_name[:11] + ".."
    return log_name


class WhoAmI(typing.NamedTuple):
    """
    Data-class to store Authenticatable information in.

    Attributes
    ----------
    type_: str
        The type of the authenticatable (user or node).
    id_: int
        The id of the authenticatable.
    name: str
        The name of the authenticatable.
    organization_name: str
        The name of the organization of the authenticatable.
    organization_id: int
        The id of the organization of the authenticatable.
    """
    type_: str
    id_: int
    name: str
    organization_name: str
    organization_id: int

    def __repr__(self) -> str:
        return (f"<WhoAmI "
                f"name={self.name}, "
                f"type={self.type_}, "
                f"organization={self.organization_name}, "
                f"(id={self.organization_id})"
                ">")


class Singleton(type):
    """
    Singleton metaclass. It allows us to create just a single instance of a
    class to which it is the metaclass.
    """
    _instances = {}

    def __call__(cls, *args, **kwargs) -> object:
        """
        When the class is called, return an instance of the class. If the
        instance already exists, return that instance.
        """
        if cls not in cls._instances:
            instance = super(Singleton, cls).__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


def bytes_to_base64s(bytes_: bytes) -> str:
    """
    Convert bytes into base64 encoded string.

    Parameters
    ----------
    bytes_: bytes
        The bytes to convert.

    Returns
    -------
    str
        The base64 encoded string.
    """
    return base64.b64encode(bytes_).decode(STRING_ENCODING)


def base64s_to_bytes(bytes_string: str) -> bytes:
    """
    Convert base64 encoded string to bytes.

    Parameters
    ----------
    bytes_string: str
        The base64 encoded string.

    Returns
    -------
    bytes
        The encoded string converted to bytes.
    """
    return base64.b64decode(bytes_string.encode(STRING_ENCODING))


#
# CLI prints
#
def echo(msg: str, level: str = "info") -> None:
    """
    Print a message to the CLI.

    Parameters
    ----------
    msg: str
        The message to print.
    level: str
        The level of the message. Can be one of: "error", "warn", "info",
        "debug".
    """
    type_ = {
        "error": f"[{Fore.RED}error{Style.RESET_ALL}]",
        "warn": f"[{Fore.YELLOW}warn {Style.RESET_ALL}]",
        "info": f"[{Fore.GREEN}info {Style.RESET_ALL}]",
        "debug": f"[{Fore.CYAN}debug{Style.RESET_ALL}]",
    }.get(level)
    click.echo(f"{type_:16} - {msg}")


def info(msg: str) -> None:
    """
    Print an info message to the CLI.

    Parameters
    ----------
    msg: str
        The message to print.
    """
    echo(msg, "info")


def warning(msg: str) -> None:
    """
    Print a warning message to the CLI.

    Parameters
    ----------
    msg: str
        The message to print.
    """
    echo(msg, "warn")


def error(msg: str) -> None:
    """
    Print an error message to the CLI.

    Parameters
    ----------
    msg: str
        The message to print.
    """
    echo(msg, "error")


def debug(msg: str) -> None:
    """
    Print a debug message to the CLI.

    Parameters
    ----------
    msg: str
        The message to print.
    """
    echo(msg, "debug")


class ClickLogger:
    """"Logs output to the click interface."""

    @staticmethod
    def info(msg: str) -> None:
        """
        Print an info message to the click interface.

        Parameters
        ----------
        msg: str
            The message to print.
        """
        info(msg)

    @staticmethod
    def warn(msg: str) -> None:
        """
        Print a warning message to the click interface.

        Parameters
        ----------
        msg: str
            The message to print.
        """
        warning(msg)

    @staticmethod
    def error(msg: str) -> None:
        """
        Print an error message to the click interface.

        Parameters
        ----------
        msg: str
            The message to print.
        """
        error(msg)

    @staticmethod
    def debug(msg: str) -> None:
        """
        Print a debug message to the click interface.

        Parameters
        ----------
        msg: str
            The message to print.
        """
        debug(msg)


def check_config_writeable(system_folders: bool = False) -> bool:
    """
    Check if the user has write permissions to create the configuration file.

    Parameters
    ----------
    system_folders: bool
        Whether to check the system folders or the user folders.

    Returns
    -------
    bool
        Whether the user has write permissions to create the configuration
        file or not.
    """
    dirs = appdirs.AppDirs()
    dirs_to_check = get_config_path(dirs, system_folders=system_folders)
    w_ok = True
    for dir_ in dirs_to_check:
        if not os.path.isdir(dir_):
            warning(f"Target directory '{dir_}' for configuration file does "
                    "not exist.")
            w_ok = False
        elif not os.access(dir_, os.W_OK):
            warning(f"No write permissions at '{dir_}'.")
            w_ok = False

    return w_ok


def get_config_path(dirs: appdirs.AppDirs,
                    system_folders: bool = False) -> str:
    """
    Get the path to the configuration directory.

    Parameters
    ----------
    dirs: appdirs.AppDirs
        The appdirs object.
    system_folders: bool
        Whether to get path to the system folders or the user folders.

    Returns
    -------
    str
        The path to the configuration directory.
    """
    if system_folders:
        config_dir = dirs.site_config_dir
        if 'xdg' in config_dir:
            config_dir = f'/etc/{APPNAME}'
        return config_dir
    else:
        return dirs.user_config_dir


def is_ip_address(ip: str) -> bool:
    """
    Test if input IP address is a valid IP address

    Parameters
    ----------
    ip: str
        IP address to validate

    Returns
    -------
    bool: whether or not IP address is valid
    """
    try:
        _ = ipaddress.ip_address(ip)
        return True
    except Exception:
        return False


def get_database_config(databases: list, label: str) -> dict | None:
    """Get database configuration from config file

    Parameters
    ----------
    databases: list[dict]
        List of database configurations
    label: str
        Label of database configuration to retrieve

    Returns
    -------
    Dict | None
        Database configuration, or None if not found
    """
    for database in databases:
        if database["label"] == label:
            return database
