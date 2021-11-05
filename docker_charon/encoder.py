from __future__ import annotations

import json
from pathlib import Path
from typing import IO, Iterator, Optional, Union
from zipfile import ZipFile

from dxf import DXF, DXFBase
from tqdm import tqdm

from docker_charon.common import Blob, Manifest, PayloadSide, progress_as_string


def add_blobs_to_zip(
    dxf_base: DXFBase,
    zip_file: ZipFile,
    blobs_to_pull: list[Blob],
    blobs_already_transferred: list[Blob],
) -> None:

    for blob_index, blob in enumerate(blobs_to_pull):
        if blob in blobs_already_transferred:
            print(
                f"{progress_as_string(blob_index, blobs_to_pull)} Skipping {blob} because it's already transferred."
            )
            continue
        print(
            f"{progress_as_string(blob_index, blobs_to_pull)} "
            f"Pulling blob {blob} and storing it in the zip"
        )
        repository_dxf = DXF.from_base(dxf_base, blob.repository)
        bytes_iterator, total_size = repository_dxf.pull_blob(blob.digest, size=True)

        # we write the blob directly to the zip file
        with tqdm(total=total_size, unit="B", unit_scale=True) as pbar:
            with zip_file.open(
                f"blobs/{blob.digest}", "w", force_zip64=True
            ) as blob_in_zip:
                for chunk in bytes_iterator:
                    blob_in_zip.write(chunk)
                    pbar.update(len(chunk))


def add_manifests_to_zip(zip_file: ZipFile, manifests: list[Manifest]) -> Iterator[str]:
    """Returns where the manifests have been stored in the zip"""
    for manifest in manifests:
        normalized_docker_image_name = manifest.docker_image_name.replace("/", "_")
        manifest_zip_path = f"manifests/{normalized_docker_image_name}"
        zip_file.writestr(manifest_zip_path, manifest.content)
        yield manifest_zip_path


def get_manifest_and_list_of_blobs_to_pull(
    dxf_base: DXFBase, docker_image: str
) -> tuple[Manifest, list[Blob]]:
    manifest = Manifest(dxf_base, docker_image, PayloadSide.ENCODER)
    return manifest, manifest.get_list_of_blobs()


def get_manifests_and_list_of_all_blobs(
    dxf_base: DXFBase, docker_images: Iterator[str]
) -> tuple[list[Manifest], list[Blob]]:
    manifests = []
    blobs_to_pull = []
    for docker_image in docker_images:
        manifest, blobs = get_manifest_and_list_of_blobs_to_pull(dxf_base, docker_image)
        manifests.append(manifest)
        blobs_to_pull += blobs
    return manifests, blobs_to_pull


def uniquify_blobs(blobs: list[Blob]) -> list[Blob]:
    result = []
    for blob in blobs:
        if blob.digest not in [x.digest for x in result]:
            result.append(blob)
    return result


def write_payload_descriptor_to_zip(
    zip_file: ZipFile,
    manifests: list[Manifest],
    manifests_paths: Iterator[str],
    docker_images_to_skip: list[str],
):
    payload_descriptor = {}
    for manifest, manifest_path in zip(manifests, manifests_paths):
        payload_descriptor[manifest.docker_image_name] = manifest_path

    # also want to add the docker images that we are skipping
    # 1) So that in the air gapped system, the user knows what was needed for the payload
    # 2) So that we can run checks on the decoder side and make sure the images actually
    #    are in the registry.
    for docker_image_to_skip in docker_images_to_skip:
        payload_descriptor[docker_image_to_skip] = None
    zip_file.writestr(
        "payload_descriptor.json", json.dumps(payload_descriptor, indent=4)
    )


def separate_images_to_transfer_and_images_to_skip(
    docker_images_to_transfer: list[str], docker_images_already_transferred: list[str]
) -> tuple[list[str], list[str]]:
    docker_images_to_transfer_with_blobs = []
    docker_images_to_skip = []
    for docker_image in docker_images_to_transfer:
        if docker_image not in docker_images_already_transferred:
            docker_images_to_transfer_with_blobs.append(docker_image)
        else:
            print(f"Skipping {docker_image} as it has already been transferred")
            docker_images_to_skip.append(docker_image)
    return docker_images_to_transfer_with_blobs, docker_images_to_skip


def create_zip_from_docker_images(
    dxf_base: DXFBase,
    docker_images_to_transfer: list[str],
    docker_images_already_transferred: list[str],
    zip_file: ZipFile,
) -> None:
    (
        docker_images_to_transfer,
        docker_images_to_skip,
    ) = separate_images_to_transfer_and_images_to_skip(
        docker_images_to_transfer, docker_images_already_transferred
    )
    manifests, blobs_to_pull = get_manifests_and_list_of_all_blobs(
        dxf_base, docker_images_to_transfer
    )
    _, blobs_already_transferred = get_manifests_and_list_of_all_blobs(
        dxf_base, docker_images_already_transferred
    )
    add_blobs_to_zip(
        dxf_base, zip_file, uniquify_blobs(blobs_to_pull), blobs_already_transferred
    )
    manifests_paths = add_manifests_to_zip(zip_file, manifests)
    write_payload_descriptor_to_zip(
        zip_file, manifests, manifests_paths, docker_images_to_skip
    )


def make_payload(
    registry: str,
    zip_file: Union[IO, Path, str],
    docker_images_to_transfer: list[str],
    docker_images_already_transferred: list[str] = [],
    secure: bool = True,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> None:
    """
    Creates a payload from a list of docker images
    All the docker images must be in the same registry.
    This is currently a limitation of the docker-charon package.

    If you are interested in multi-registries, please open an issue.

    # Arguments
        registry: The registry to pull the images from. The name of the registry
            must not be included in `docker_images_to_transfer` and
            `docker_images_already_transferred`.
        zip_file: The path to the zip file to create. It can be a `pathlib.Path` or
            a `str`. It's also possible to pass a file-like object. The payload with
            all the docker images is a single zip file.
        docker_images_to_transfer: The list of docker images to transfer. Do not include
            the registry name in the image name.
        docker_images_already_transferred: The list of docker images that have already
            been transferred to the air-gapped registry. Do not include the registry
            name in the image name.
        secure: Set to `False` if the registry doesn't support HTTPS (TLS). Default
            is `True`.
        username: The username to use for authentication to the registry. Optional if
            the registry doesn't require authentication.
        password: The password to use for authentication to the registry. Optional if
            the registry doesn't require authentication.
    """
    with DXFBase(host=registry, insecure=not secure) as dxf_base:
        if username is not None:
            dxf_base.authenticate(username, password)

        with ZipFile(zip_file, "w") as zip_file:
            create_zip_from_docker_images(
                dxf_base,
                docker_images_to_transfer,
                docker_images_already_transferred,
                zip_file,
            )
