import os
from pathlib import Path

import click
import questionary as q
from copier import run_copy

from vantage6.cli.globals import ALGORITHM_TEMPLATE_REPO
from vantage6.cli.utils import info


@click.command()
@click.option('-n', '--name', default=None, type=str,
              help="Name for your new algorithm")
@click.option('-d', '--dir', 'directory', default=None, type=str,
              help="Directory to put the algorithm into")
def cli_algorithm_create(
    name: str, directory: str
) -> dict:
    """Creates a personalized template for a new algorithm

    By answering a number of questions, a template will be created that will
    simplify the creation of a new algorithm. The goal is that the algorithm
    developer only focuses on the algorithm code rather than fitting it to
    the vantage6 infrastructure.

    The created template will contain a Python package with a Dockerfile that
    can be used to build an appropriate Docker image that can be used as a
    vantage6 algorithm.
    """
    if not name:
        name = q.text("Name of your new algorithm:").ask()

    if not directory:
        default_dir = str(Path(os.getcwd()) / name)
        directory = q.text(
            "Directory to put the algorithm in:",
            default=default_dir
        ).ask()

    run_copy(
        ALGORITHM_TEMPLATE_REPO,
        directory,
        data={'algorithm_name': name}
    )
    info("Template created!")
    info(f"You can find your new algorithm in: {directory}")
