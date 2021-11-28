import os
import sys
import tempfile
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
    zip_file: str,
    docker_images_to_transfer: str = typer.Argument(
        ...,
        help="docker images to transfer, a commas delimited list of docker image names. "
        "Do not include the registry name.",
    ),
    already_transferred: Optional[str] = typer.Option(
        None,
        help="docker images already present in the remote registry, "
        "a commas delimited list of docker image names. Do not include the registry name.",
    ),
    secure: bool = typer.Option(
        True,
        "--insecure",
        help="Use --insecure if the registry uses http instead of https",
        show_default=False,
    ),
    username: Optional[str] = typer.Option(
        None,
        help=f"The username to use to connect to the registry. If you want more "
        f"security and don't want your username to appear in your shell "
        f"history, you can also use the environment variable {DOCKER_CHARON_USERNAME}",
    ),
    password: Optional[str] = typer.Option(
        None,
        help=f"The password to use to connect to the registry. If you want more "
        f"security and don't want your password to appear in your shell "
        f"history, you can also use the environment variable {DOCKER_CHARON_PASSWORD}",
    ),
):
    """Create a payload (.zip file) with docker images inside. This zip file
    can then be unpacked into a registry in another system.

    By providing images that were already transferred to the new registry, you can reduce the size
    and creation time of the payload. This is because docker-charon only takes the layers
    that were not already transferred.

    When specifying the zip file, you can use a relative path, an absolute path, or '-' for stdout.
    """
    docker_images_to_transfer = docker_images_to_transfer.strip().split(",")
    if already_transferred is None:
        already_transferred = []
    else:
        already_transferred = already_transferred.strip().split(",")

    # the user may want for security to pass credentials to docker-charon with env
    # variables.
    username = username or os.environ.get(DOCKER_CHARON_USERNAME)
    password = password or os.environ.get(DOCKER_CHARON_PASSWORD)
    if zip_file != "-":
        docker_charon.make_payload(
            registry,
            zip_file,
            docker_images_to_transfer,
            already_transferred,
            secure,
            username,
            password,
        )
    elif zip_file == "-":
        # to avoid messing with unseekable streams, we need to write to a temp file
        # and then copy it to stdout
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_file = Path(temporary_directory) / "payload.zip"
            docker_charon.make_payload(
                registry,
                temporary_file,
                docker_images_to_transfer,
                already_transferred,
                secure,
                username,
                password,
            )
            with open(temporary_file, "rb") as f:
                while data := f.read(1024):
                    sys.stdout.buffer.write(data)


@app.command()
def push_payload(
    registry: str,
    zip_file: str,
    strict: bool = False,
    secure: bool = typer.Option(
        True,
        "--insecure",
        help="Use --insecure if the registry uses http instead of https",
        show_default=False,
    ),
    username: Optional[str] = typer.Option(
        None,
        help=f"The username to use to connect to the registry. If you want more "
        f"security and don't want your username to appear in your shell "
        f"history, you can also use the environment variable {DOCKER_CHARON_USERNAME}",
    ),
    password: Optional[str] = typer.Option(
        None,
        help=f"The password to use to connect to the registry. If you want more "
        f"security and don't want your password to appear in your shell "
        f"history, you can also use the environment variable {DOCKER_CHARON_PASSWORD}",
    ),
):
    """Unpack the payload (.zip file) into a docker registry.

    The zip file must have been created by 'docker-charon make-payload ...'

    When specifying the zip file, you can use a relative path, an absolute path, or '-' for stdin.
    This command will output to stdout the list of images that were transferred.
    One image per line.
    """
    # the user may want for security to pass credentials to docker-charon with env
    # variables.
    username = username or os.environ.get(DOCKER_CHARON_USERNAME)
    password = password or os.environ.get(DOCKER_CHARON_PASSWORD)
    if zip_file != "-":
        images_pushed = docker_charon.push_payload(
            registry,
            zip_file,
            strict,
            secure,
            username,
            password,
        )
    elif zip_file == "-":
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_file = Path(temporary_directory) / "payload.zip"
            with open(temporary_file, "wb") as f:
                while data := sys.stdin.buffer.read(1024):
                    f.write(data)
            images_pushed = docker_charon.push_payload(
                registry,
                temporary_file,
                strict,
                secure,
                username,
                password,
            )

    print("List of docker images pushed to the registry:", file=sys.stderr)
    for image in images_pushed:
        print(image)


def main():
    app()


if __name__ == "__main__":
    main()
