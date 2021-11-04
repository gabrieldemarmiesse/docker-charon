from __future__ import annotations

import json
from pathlib import Path
from typing import IO, Iterator, Optional, Union
from zipfile import ZipFile

from dxf import DXF, DXFBase

from docker_charon.common import (
    Manifest,
    PayloadSide,
    file_to_generator,
    progress_as_string,
)


def push_payload_to_registry(
    registry: str,
    zip_file: Union[IO, Path, str],
    secure: bool = True,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> list[str]:
    """Push the payload to the registry.

    It will iterate over the docker images and push the blobs and the manifests.

    # Arguments
        registry: the registry to push to.
        zip_file: the zip file containing the payload. It can be a `pathlib.Path`, a `str`
            or a file-like object.
        secure: whether to use TLS (HTTPS) or not to connect to the registry,
            default is True.
        username: the username to use to connect to the registry. Optional
            if the registry does not require authentication.
        password: the password to use to connect to the registry. Optional
            if the registry does not require authentication.

    # Returns
        The list of docker images loaded in the registry
        It also includes the list of docker images that were already present
        in the registry and were not included in the payload to optimize the size.
        In other words, it's the argument `docker_images_to_transfer` that you passed
        to the function `docker_charon.make_payload(...)`.
    """
    with DXFBase(host=registry, insecure=not secure) as dxf_base:
        if username is not None:
            dxf_base.authenticate(username, password)
        with ZipFile(zip_file, "r") as zip_file:
            return list(load_zip_images_in_registry(dxf_base, zip_file))


def push_all_blobs_from_manifest(
    dxf_base: DXFBase, zip_file: ZipFile, manifest: Manifest
) -> None:
    list_of_blobs = manifest.get_list_of_blobs()
    for blob_index, blob in enumerate(list_of_blobs):
        print(
            f"{progress_as_string(blob_index, list_of_blobs)} " f"Pushing blob {blob}"
        )
        dxf = DXF.from_base(dxf_base, blob.repository)

        # we try to open the file in the zip and push it. If the file doesn't
        # exists in the zip, it means that it's already been pushed.
        try:
            with zip_file.open(f"blobs/{blob.digest}", "r") as blob_in_zip:
                dxf.push_blob(data=file_to_generator(blob_in_zip), digest=blob.digest)
        except KeyError:
            print(f"Skipping {blob} as it has already been pushed")


def load_single_image_from_zip_in_registry(
    dxf_base: DXFBase, zip_file: ZipFile, docker_image: str, manifest_path_in_zip: str
) -> None:
    print(f"Loading image {docker_image}")
    manifest_content = zip_file.read(manifest_path_in_zip).decode()
    manifest = Manifest(
        dxf_base, docker_image, PayloadSide.DECODER, content=manifest_content
    )
    push_all_blobs_from_manifest(dxf_base, zip_file, manifest)
    dxf = DXF.from_base(dxf_base, manifest.repository)
    dxf.set_manifest(manifest.tag, manifest.content)


def load_zip_images_in_registry(dxf_base: DXFBase, zip_file: ZipFile) -> Iterator[str]:
    payload_descriptor = json.loads(zip_file.read("payload_descriptor.json").decode())
    for docker_image, manifest_path_in_zip in payload_descriptor.items():
        load_single_image_from_zip_in_registry(
            dxf_base, zip_file, docker_image, manifest_path_in_zip
        )
        yield docker_image
