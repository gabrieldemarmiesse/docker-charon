import os
from pathlib import Path
from typing import Optional

import typer

import docker_charon

DOCKER_CHARON_USERNAME = "DOCKER_CHARON_USERNAME"
DOCKER_CHARON_PASSWORD = "DOCKER_CHARON_PASSWORD"

app = typer.Typer()


@app.command()
def make_payload(
    registry: str,
    zip_file: Path,
    docker_images_to_transfer: str = typer.Argument(
        ...,
        help="docker images to transfer, a commas delimited list of docker image names",
    ),
    already_transferred: Optional[str] = typer.Option(
        None,
        help="docker images already present in the remote registry, "
        "a commas delimited list of docker image names",
    ),
    secure: bool = typer.Option(
        True,
        "--unsecure",
        help="Use --unsecure if the registry uses http instead of https",
        show_default=False,
    ),
    username: Optional[str] = None,
    password: Optional[str] = None,
):
    docker_images_to_transfer = docker_images_to_transfer.strip().split(",")
    if already_transferred is None:
        already_transferred = []
    else:
        already_transferred = already_transferred.strip().split(",")

    # the user may want for security to pass credentials to docker-charon with env
    # variables.
    username = username or os.environ.get(DOCKER_CHARON_USERNAME)
    password = password or os.environ.get(DOCKER_CHARON_PASSWORD)

    docker_charon.make_payload(
        registry,
        zip_file,
        docker_images_to_transfer,
        already_transferred,
        secure,
        username,
        password,
    )


@app.command()
def push_payload(
    registry: str,
    zip_file: Path,
    strict: bool = False,
    secure: bool = typer.Option(
        True,
        "--unsecure",
        help="Use --unsecure if the registry uses http instead of https",
        show_default=False,
    ),
    username: Optional[str] = None,
    password: Optional[str] = None,
):
    # the user may want for security to pass credentials to docker-charon with env
    # variables.
    username = username or os.environ.get(DOCKER_CHARON_USERNAME)
    password = password or os.environ.get(DOCKER_CHARON_PASSWORD)

    docker_charon.push_payload_to_registry(
        registry, zip_file, strict, secure, username, password
    )


def main():
    app()
