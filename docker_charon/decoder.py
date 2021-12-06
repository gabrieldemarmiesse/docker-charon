from __future__ import annotations

import sys
import warnings
from pathlib import Path
from typing import IO, Iterator, Optional, Union
from zipfile import ZipFile

import requests
from dxf import DXF, DXFBase

from docker_charon.common import (
    Authenticator,
    Blob,
    BlobLocationInRegistry,
    BlobPathInZip,
    Manifest,
    PayloadDescriptor,
    PayloadSide,
    file_to_generator,
    get_repo_and_tag,
    progress_as_string,
)


class ManifestNotFound(Exception):
    pass


class BlobNotFound(Exception):
    pass


def push_payload(
    zip_file: Union[IO, Path, str],
    strict: bool = False,
    registry: str = "registry-1.docker.io",
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
        strict: `False` by default. If True, it will raise an error if the
            some blobs/images are missing.
            That can happen if the user
            set an image in `docker_images_already_transferred`
            that is not in the registry.
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
    authenticator = Authenticator(username, password)

    with DXFBase(
        host=registry, auth=authenticator.auth, insecure=not secure
    ) as dxf_base:
        with ZipFile(zip_file, "r") as zip_file:
            return list(load_zip_images_in_registry(dxf_base, zip_file, strict))


def push_all_blobs_from_manifest(
    dxf_base: DXFBase,
    zip_file: ZipFile,
    manifest: Manifest,
    blobs_paths: dict,
) -> None:
    list_of_blobs = manifest.get_list_of_blobs()
    for blob_index, blob in enumerate(list_of_blobs):
        print(progress_as_string(blob_index, list_of_blobs), end=" ", file=sys.stderr)

        blob_path = blobs_paths[blob.digest]

        if isinstance(blob_path, BlobPathInZip):
            print(f"pushing blob {blob}", file=sys.stderr)
            dxf = DXF.from_base(dxf_base, blob.repository)
            # we try to open the file in the zip and push it. If the file doesn't
            # exists in the zip, it means that it's already been pushed.
            with zip_file.open(blob_path.zip_path, "r") as blob_in_zip:
                dxf.push_blob(data=file_to_generator(blob_in_zip), digest=blob.digest)
        elif isinstance(blob_path, BlobLocationInRegistry):
            blob_in_registry = Blob(dxf_base, blob.digest, blob_path.repository)
            transfer_blob_between_two_repositories(blob_in_registry, blob.repository)


def load_single_image_from_zip_in_registry(
    dxf_base: DXFBase,
    zip_file: ZipFile,
    docker_image: str,
    manifest_path_in_zip: str,
    blobs_paths: dict[str, Union[BlobPathInZip, BlobLocationInRegistry]],
) -> None:
    print(f"Loading image {docker_image}", file=sys.stderr)
    manifest_content = zip_file.read(manifest_path_in_zip).decode()
    manifest = Manifest(
        dxf_base, docker_image, PayloadSide.DECODER, content=manifest_content
    )
    push_all_blobs_from_manifest(dxf_base, zip_file, manifest, blobs_paths)
    dxf = DXF.from_base(dxf_base, manifest.repository)
    dxf.set_manifest(manifest.tag, manifest.content)


def check_if_the_docker_image_is_in_the_registry(
    dxf_base: DXFBase, docker_image: str, strict: bool
):
    """we skipped this image because the user said it was in the registry. Let's
    check if it's true. Raise an warning/error if not.
    """
    repo, tag = get_repo_and_tag(docker_image)
    dxf = DXF.from_base(dxf_base, repo)
    try:
        dxf.get_manifest(tag)
    except requests.HTTPError as e:
        if e.response.status_code != 404:
            raise
        error_message = (
            f"The docker image {docker_image} is not present in the "
            f"registry. But when making the payload, it was specified in "
            f"`docker_images_already_transferred`."
        )
        if strict:
            raise ManifestNotFound(
                f"{error_message}\n"
                f"If you still want to unpack your payload, set `strict=False`."
            )
        else:
            warnings.warn(error_message, UserWarning)
            return
    print(f"Skipping {docker_image} as its already in the registry", file=sys.stderr)


def load_zip_images_in_registry(
    dxf_base: DXFBase, zip_file: ZipFile, strict: bool
) -> Iterator[str]:
    payload_descriptor = get_payload_descriptor(zip_file)
    for (
        docker_image,
        manifest_path_in_zip,
    ) in payload_descriptor.manifests_paths.items():
        if manifest_path_in_zip is None:
            check_if_the_docker_image_is_in_the_registry(dxf_base, docker_image, strict)
        else:
            load_single_image_from_zip_in_registry(
                dxf_base,
                zip_file,
                docker_image,
                manifest_path_in_zip,
                payload_descriptor.blobs_paths,
            )
        yield docker_image


def get_payload_descriptor(zip_file: ZipFile) -> PayloadDescriptor:
    return PayloadDescriptor.parse_raw(
        zip_file.read("payload_descriptor.json").decode()
    )


def transfer_blob_between_two_repositories(blob: Blob, new_repository: str):
    """This function could be replace by a blob mount but it's not yet
    implemented by DXF.

    We can always use this as a fallback if the registry doesn't allow blob mounting.

    If the source and destination are both the same repo, it's a no-op,
    same if the blob is already at the right place.
    """
    dxf_current_repository = DXF.from_base(blob.dxf_base, blob.repository)
    dxf_new_repository = DXF.from_base(blob.dxf_base, new_repository)

    if blob_exist(dxf_new_repository, blob.digest):
        print(f"Blob {blob} is already in the registry", file=sys.stderr)
        return

    # transfer the blob
    print(f"Mounting {blob} to {new_repository}", file=sys.stderr)
    bytes_generator = dxf_current_repository.pull_blob(blob.digest)
    dxf_new_repository.push_blob(data=bytes_generator, digest=blob.digest)


def blob_exist(dxf: DXF, digest: str) -> bool:
    try:
        dxf.blob_size(digest)
    except requests.HTTPError as e:
        if e.response.status_code != 404:
            raise
        return False
    return True
