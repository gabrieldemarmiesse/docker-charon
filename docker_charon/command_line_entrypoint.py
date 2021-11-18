from pathlib import Path
from typing import Optional

import typer

import docker_charon

app = typer.Typer()


@app.command()
def make_payload(
    registry: str,
    zip_file: Path,
    docker_images_to_transfer: list[str],
    docker_images_already_transferred: list[str] = [],
    secure: bool = True,
    username: Optional[str] = None,
    password: Optional[str] = None,
):
    docker_charon.make_payload(
        registry,
        zip_file,
        docker_images_to_transfer,
        docker_images_already_transferred,
        secure,
        username,
        password,
    )


@app.command()
def push_payload(
    registry: str,
    zip_file: Path,
    strict: bool = False,
    secure: bool = True,
    username: Optional[str] = None,
    password: Optional[str] = None,
):
    docker_charon.push_payload_to_registry(
        registry, zip_file, strict, secure, username, password
    )


def main():
    app()
