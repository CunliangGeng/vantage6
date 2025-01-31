"""
Common functions that are used in node CLI commands
"""
from typing import Iterable

import questionary as q
import docker
from colorama import Fore, Style

from vantage6.common import error, info, debug
from vantage6.common.globals import STRING_ENCODING, APPNAME
from vantage6.client import UserClient

from vantage6.cli.context import NodeContext
from vantage6.cli.configuration_wizard import select_configuration_questionaire


#  helper functions
def print_log_worker(logs_stream: Iterable[bytes]) -> None:
    """
    Print the logs from the logs stream.

    Parameters
    ----------
    logs_stream : Iterable[bytes]
        Output of the container.attach() method
    """
    for log in logs_stream:
        print(log.decode(STRING_ENCODING), end="")


def create_client(ctx: NodeContext) -> UserClient:
    """
    Create a client instance.

    Parameters
    ----------
    ctx : NodeContext
        Context of the node loaded from the configuration file
    Returns
    -------
    UserClient
        vantage6 client
    """
    host = ctx.config['server_url']
    # if the server is run locally, we need to use localhost here instead of
    # the host address of docker
    if host in ['http://host.docker.internal', 'http://172.17.0.1']:
        host = 'http://localhost'
    port = ctx.config['port']
    api_path = ctx.config['api_path']
    info(f"Connecting to server at '{host}:{port}{api_path}'")
    return UserClient(host, port, api_path, log_level='warn')


def create_client_and_authenticate(ctx: NodeContext) -> UserClient:
    """
    Generate a client and authenticate with the server.

    Parameters
    ----------
    ctx : NodeContext
        Context of the node loaded from the configuration file

    Returns
    -------
    UserClient
        vantage6 client
    """
    client = create_client(ctx)

    username = q.text("Username:").ask()
    password = q.password("Password:").ask()

    try:
        client.authenticate(username, password)

    except Exception as exc:
        error("Could not authenticate with server!")
        debug(exc)
        exit(1)

    return client


def select_node(name: str, system_folders: bool) -> tuple[str, str]:
    """
    Let user select node through questionnaire if name is not given.

    Returns
    -------
    str
        Name of the configuration file
    """
    name = name if name else \
        select_configuration_questionaire("node", system_folders)

    # raise error if config could not be found
    if not NodeContext.config_exists(name, system_folders):
        error(
            f"The configuration {Fore.RED}{name}{Style.RESET_ALL} could "
            f"not be found."
        )
        exit(1)
    return name


def find_running_node_names(client: docker.DockerClient) -> list[str]:
    """
    Returns a list of names of running nodes.

    Parameters
    ----------
    client : docker.DockerClient
        Docker client instance

    Returns
    -------
    list[str]
        List of names of running nodes
    """
    running_nodes = client.containers.list(
        filters={"label": f"{APPNAME}-type=node"})
    return [node.name for node in running_nodes]
