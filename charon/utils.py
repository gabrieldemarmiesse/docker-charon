import contextlib
import json
from enum import Enum
from pathlib import Path
from typing import IO, Iterator, Optional, Union
from zipfile import ZipFile

from dxf import DXF, DXFBase
from tqdm import tqdm


class PayloadSide(Enum):
    ENCODER = "ENCODER"
    DECODER = "DECODER"


class Blob:
    def __init__(self, dxf_base: DXFBase, digest: str, repository: str):
        self.dxf_base = dxf_base
        self.digest = digest
        self.repository = repository


class Manifest:
    def __init__(
        self,
        dxf_base: DXFBase,
        docker_image_name: str,
        payload_side: PayloadSide,
        content: Optional[str] = None,
    ):
        self.dxf_base = dxf_base
        self.docker_image_name = docker_image_name
        self.payload_side = payload_side
        self._content = content

    @property
    def repository(self) -> str:
        return self.docker_image_name.split(":")[0]

    @property
    def tag(self) -> str:
        return self.docker_image_name.split(":")[1]

    @property
    def content(self) -> str:
        if self._content is None:
            if self.payload_side == PayloadSide.DECODER:
                raise ValueError(
                    "This makes no sense to fetch the manifest from "
                    "the registry if you're decoding the zip"
                )
            dxf = DXF.from_base(self.dxf_base, self.repository)
            self._content = dxf.get_manifest(self.tag)
        return self._content

    def get_list_of_blobs(self) -> list[Blob]:
        manifest_dict = json.loads(self.content)
        result: list[Blob] = [
            Blob(self.dxf_base, manifest_dict["config"]["digest"], self.repository)
        ]
        for layer in manifest_dict["layers"]:
            result.append(Blob(self.dxf_base, layer["digest"], self.repository))
        return result


def get_manifest_and_list_of_blobs_to_pull(
    dxf_base: DXFBase, docker_image: str
) -> tuple[Manifest, list[Blob]]:
    manifest = Manifest(dxf_base, docker_image, PayloadSide.ENCODER)
    return manifest, manifest.get_list_of_blobs()


def progress_as_string(index: int, container: list) -> str:
    return f"[{index+1}/{len(container)}]"


def add_blobs_to_zip(
    dxf_base: DXFBase, zip_file: ZipFile, blobs_to_pull: list[Blob]
) -> None:

    for blob_index, blob in enumerate(blobs_to_pull):
        print(
            f"{progress_as_string(blob_index, blobs_to_pull)} "
            f"Pulling blob {blob} and storing it in the zip"
        )
        repository_dxf = DXF.from_base(dxf_base, blob.repository)
        bytes_iterator, total_size = repository_dxf.pull_blob(blob.digest, size=True)

        # we write the blob directly to the zip file
        with tqdm(total=total_size) as pbar:
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


def get_manifests_and_list_of_all_blobs(
    dxf_base: DXFBase, docker_images: list[str]
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
    zip_file: ZipFile, manifests: list[Manifest], manifests_paths: Iterator[str]
):
    payload_descriptor = {}
    for manifest, manifest_path in zip(manifests, manifests_paths):
        payload_descriptor[manifest.docker_image_name] = manifest_path
    zip_file.writestr(
        "payload_descriptor.json", json.dumps(payload_descriptor, indent=4)
    )


def create_zip_from_docker_images(
    dxf_base: DXFBase, docker_images: list[str], zip_file: ZipFile
) -> None:
    manifests, blobs_to_pull = get_manifests_and_list_of_all_blobs(
        dxf_base, docker_images
    )
    add_blobs_to_zip(dxf_base, zip_file, uniquify_blobs(blobs_to_pull))
    manifests_paths = add_manifests_to_zip(zip_file, manifests)
    write_payload_descriptor_to_zip(zip_file, manifests, manifests_paths)


def make_payload(
    docker_images: list[str],
    registry: str,
    zip_file: Union[IO, Path, str],
    insecure: bool = False,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> None:
    """
    Creates a payload from a list of docker images
    """
    with DXFBase(host=registry, insecure=insecure) as dxf_base:
        if username is not None:
            dxf_base.authenticate(username, password)

        with ZipFile(zip_file, "w") as zip_file:
            create_zip_from_docker_images(dxf_base, docker_images, zip_file)


def file_to_generator(file_like: IO) -> Iterator[bytes]:
    while True:
        chunk = file_like.read(2 ** 15)
        if not chunk:
            break
        yield chunk


def push_all_blobs_from_manifest(
    dxf_base: DXFBase, zip_file: ZipFile, manifest: Manifest
) -> None:
    list_of_blobs = manifest.get_list_of_blobs()
    for blob_index, blob in enumerate(list_of_blobs):
        print(
            f"{progress_as_string(blob_index, list_of_blobs)} " f"Pushing blob {blob}"
        )
        dxf = DXF.from_base(dxf_base, blob.repository)
        with zip_file.open(f"blobs/{blob.digest}", "r") as blob_in_zip:
            dxf.push_blob(data=file_to_generator(blob_in_zip), digest=blob.digest)


def load_single_image_from_zip_in_registry(
    dxf_base: DXFBase, zip_file: ZipFile, docker_image: str, manifest_path_in_zip: str
) -> None:
    print(f"Loading image {docker_image}")
    manifest_content = zip_file.read(manifest_path_in_zip).decode()
    manifest = Manifest(
        dxf_base, docker_image, PayloadSide.DECODER, content=manifest_content
    )
    push_all_blobs_from_manifest(dxf_base, zip_file, manifest)


def load_zip_images_in_registry(dxf_base: DXFBase, zip_file_path: Path) -> None:
    with ZipFile(zip_file_path, "r") as zip_file:
        payload_descriptor = json.loads(
            zip_file.read("payload_descriptor.json").decode()
        )
        for docker_image, manifest_path_in_zip in payload_descriptor.items():
            load_single_image_from_zip_in_registry(
                dxf_base, zip_file, docker_image, manifest_path_in_zip
            )
