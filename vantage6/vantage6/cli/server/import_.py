import os
from threading import Thread

import click
import docker
from sqlalchemy.engine.url import make_url

from vantage6.common import info, warning
from vantage6.common.docker.addons import check_docker_running
from vantage6.common.globals import (
    APPNAME,
    DEFAULT_DOCKER_REGISTRY,
    DEFAULT_SERVER_IMAGE,
)
from vantage6.cli.context import ServerContext
from vantage6.cli.utils import check_config_name_allowed
from vantage6.cli.server.common import click_insert_context, print_log_worker


# TODO this method has a lot of duplicated code from `start`
@click.command()
@click.argument('file', type=click.Path(exists=True))
@click.option('--drop-all', is_flag=True, default=False,
              help="Drop all existing data before importing")
@click.option('-i', '--image', default=None, help="Node Docker image to use")
@click.option('--mount-src', default='',
              help="Override vantage6 source code in container with the source"
                   " code in this path")
@click.option('--keep/--auto-remove', default=False,
              help="Keep image after finishing. Useful for debugging")
@click.option('--wait', default=False, help="Wait for the import to finish")
@click_insert_context
def cli_server_import(
    ctx: ServerContext, file: str, drop_all: bool, image: str, mount_src: str,
    keep: bool, wait: bool
) -> None:
    """
    Import vantage6 resources into a server instance.

    This allows you to create organizations, collaborations, users, tasks, etc
    from a yaml file.

    The FILE_ argument should be a path to a yaml file containing the vantage6
    formatted data to import.
    """
    # will print an error if not
    check_docker_running()

    info("Starting server...")
    info("Finding Docker daemon.")
    docker_client = docker.from_env()

    # check if name is allowed for docker volume, else exit
    check_config_name_allowed(ctx.name)

    # pull latest Docker image
    if image is None:
        image = ctx.config.get(
            "image",
            f"{DEFAULT_DOCKER_REGISTRY}/{DEFAULT_SERVER_IMAGE}"
        )
    info(f"Pulling latest server image '{image}'.")
    try:
        docker_client.images.pull(image)
    except Exception as e:
        warning(' ... Getting latest node image failed:')
        warning(f"     {e}")
    else:
        info(" ... success!")

    info("Creating mounts")
    mounts = [
        docker.types.Mount(
            "/mnt/config.yaml", str(ctx.config_file), type="bind"
        ),
        docker.types.Mount(
            "/mnt/import.yaml", str(file), type="bind"
        )
    ]

    # FIXME: code duplication with cli_server_start()
    # try to mount database
    uri = ctx.config['uri']
    url = make_url(uri)
    environment_vars = None

    if mount_src:
        mount_src = os.path.abspath(mount_src)
        mounts.append(docker.types.Mount("/vantage6", mount_src, type="bind"))

    # If host is None, we're dealing with a file-based DB, like SQLite
    if (url.host is None):
        db_path = url.database

        if not os.path.isabs(db_path):
            # We're dealing with a relative path here -> make it absolute
            db_path = ctx.data_dir / url.database

        basename = os.path.basename(db_path)
        dirname = os.path.dirname(db_path)
        os.makedirs(dirname, exist_ok=True)

        # we're mounting the entire folder that contains the database
        mounts.append(docker.types.Mount(
            "/mnt/database/", dirname, type="bind"
        ))

        environment_vars = {
            "VANTAGE6_DB_URI": f"sqlite:////mnt/database/{basename}"
        }

    else:
        warning(f"Database could not be transferred, make sure {url.host} "
                "is reachable from the Docker container")
        info("Consider using the docker-compose method to start a server")

    drop_all_ = "--drop-all" if drop_all else ""
    cmd = (f'vserver-local import -c /mnt/config.yaml {drop_all_} '
           '/mnt/import.yaml')

    info(cmd)

    info("Run Docker container")
    container = docker_client.containers.run(
        image,
        command=cmd,
        mounts=mounts,
        detach=True,
        labels={
            f"{APPNAME}-type": "server",
            "name": ctx.config_file_name
        },
        environment=environment_vars,
        auto_remove=not keep,
        tty=True
    )
    logs = container.logs(stream=True, stdout=True)
    Thread(target=print_log_worker, args=(logs,), daemon=False).start()

    info(f"Success! container id = {container.id}")

    if wait:
        container.wait()
        info("Container finished!")
