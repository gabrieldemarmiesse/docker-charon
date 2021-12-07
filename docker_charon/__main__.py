import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import typer

import docker_charon

DOCKER_CHARON_USERNAME = "DOCKER_CHARON_USERNAME"
DOCKER_CHARON_PASSWORD = "DOCKER_CHARON_PASSWORD"

app = typer.Typer()


@app.command()
def make_payload(
    docker_images_to_transfer: str = typer.Argument(
        ...,
        help="docker images to transfer, a commas delimited list of docker image names. "
        "Do not include the registry name.",
    ),
    already_transferred: Optional[str] = typer.Option(
        None,
        "--already-transferred",
        "-a",
        help="docker images already present in the remote registry, "
        "a commas delimited list of docker image names. Do not include the registry name.",
    ),
    file: Optional[str] = typer.Option(
        None,
        "--file",
        "-f",
        help="Where to write the payload zip file. "
        "If this is not provided, the payload will be written to stdout.",
    ),
    registry: str = typer.Option(
        "registry-1.docker.io",
        "--registry",
        "-r",
        show_default=False,
        help="The registry to push the payload to. It defaults to dockerhub (registry-1.docker.io)",
    ),
    secure: bool = typer.Option(
        True,
        "--insecure",
        "-i",
        help="Use --insecure if the registry uses http instead of https",
        show_default=False,
    ),
    username: Optional[str] = typer.Option(
        None,
        "--username",
        "-u",
        help=f"The username to use to connect to the registry. If you want more "
        f"security and don't want your username to appear in your shell "
        f"history, you can also use the environment variable {DOCKER_CHARON_USERNAME}",
    ),
    password: Optional[str] = typer.Option(
        None,
        "--password",
        "-p",
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

    The payload is written to stdout by default. You can provide a file path to write the payload to
    by using the --file (or -f) option.
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
    if file is None:
        file = sys.stdout.buffer
    docker_charon.make_payload(
        file,
        docker_images_to_transfer,
        already_transferred,
        registry,
        secure,
        username,
        password,
    )


@contextmanager
def open_file_or_stdin(file_path: Optional[str]):
    if file_path is None:
        # we need to read the zip file from stdin
        # since the central directory is at the end of the file
        # we need to store the stream in a temporary file
        # buffering would be useless here
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_file = Path(temporary_directory) / "payload.zip"
            with open(temporary_file, "ab+") as f:
                while data := sys.stdin.buffer.read(1024):
                    f.write(data)
                f.seek(0)
                yield f
    else:
        yield file_path


@app.command()
def push_payload(
    file: Optional[str] = typer.Option(
        None,
        "--file",
        "-f",
        help="The payload zip file. If this is not provided, the payload will be read from stdin.",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        "-s",
        help="Fails if there is a mismatch between what was given with --already-transferred "
        "and what is in the registry.",
    ),
    registry: str = typer.Option(
        "registry-1.docker.io",
        "--registry",
        "-r",
        help="The registry to push the payload to. It defaults to dockerhub (registry-1.docker.io)",
    ),
    secure: bool = typer.Option(
        True,
        "--insecure",
        "-i",
        help="Use --insecure if the registry uses http instead of https",
        show_default=False,
    ),
    username: Optional[str] = typer.Option(
        None,
        "--username",
        "-u",
        help=f"The username to use to connect to the registry. If you want more "
        f"security and don't want your username to appear in your shell "
        f"history, you can also use the environment variable {DOCKER_CHARON_USERNAME}",
    ),
    password: Optional[str] = typer.Option(
        None,
        "--password",
        "-p",
        help=f"The password to use to connect to the registry. If you want more "
        f"security and don't want your password to appear in your shell "
        f"history, you can also use the environment variable {DOCKER_CHARON_PASSWORD}",
    ),
):
    """Unpack the payload (.zip file) into a docker registry.

    The zip file must have been created by 'docker-charon make-payload ...'

    This command will output to stdout the list of images that were transferred.
    One image per line.

    By default, the payload is read from stdin. You can provide a file path to read the payload from
    by using the --file (or -f) option.
    """
    # the user may want for security to pass credentials to docker-charon with env
    # variables.
    username = username or os.environ.get(DOCKER_CHARON_USERNAME)
    password = password or os.environ.get(DOCKER_CHARON_PASSWORD)
    with open_file_or_stdin(file) as f:
        images_pushed = docker_charon.push_payload(
            f,
            strict,
            registry,
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
