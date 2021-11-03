import base64
import os
from zipfile import ZipFile
import json
from dxf import DXF, DXFBase
from pathlib import Path
from tqdm import tqdm
from python_on_whales import docker
from typing import Optional, Iterator


class Blob:
    def __init__(self, dxf_base: DXFBase, digest: str, repository: str):
        self.dxf_base = dxf_base
        self.digest = digest
        self.repository = repository


class Manifest:
    def __init__(self, dxf_base: DXFBase, docker_image_name: str):
        self.dxf_base = dxf_base
        self.docker_image_name = docker_image_name
        self._content = None

    @property
    def repository(self) -> str:
        return self.docker_image_name.split(":")[0]

    @property
    def tag(self) -> str:
        return self.docker_image_name.split(":")[1]

    @property
    def content(self) -> str:
        if self._content is None:
            dxf = DXF.from_base(self.dxf_base, self.repository)
            self._content = dxf.get_manifest(self.tag)
        return self._content

    def get_list_of_blobs(self) -> list[Blob]:
        manifest_dict = json.loads(self.content)
        result: list[Blob] = [Blob(self.dxf_base, manifest_dict["config"]["digest"], self.repository)]
        for layer in manifest_dict["layers"]:
            result.append(Blob(self.dxf_base, layer["digest"], self.repository))
        return result


def get_manifest_and_list_of_blobs_to_pull(dxf_base: DXFBase, docker_image: str) -> tuple[Manifest, list[Blob]]:
    manifest = Manifest(dxf_base, docker_image)
    return manifest, manifest.get_list_of_blobs()



def add_blobs_to_zip(dxf_base: DXFBase, zip_file: ZipFile, blobs_to_pull: list[Blob]) -> None:

    for blob_index, blob in enumerate(blobs_to_pull):
        progress = f"[{blob_index+1}/{len(blobs_to_pull)}]"
        print(f"{progress} Pulling blob {blob} and storing it in the zip")

        repository_dxf = DXF.from_base(dxf_base, blob.repository)
        bytes_iterator, total_size = repository_dxf.pull_blob(blob.digest, size=True)

        # we write the blob directly to the zip file
        with tqdm(total=total_size) as pbar:
            with zip_file.open(f"blobs/{blob.digest}", "w", force_zip64=True) as blob_in_zip:
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


def get_manifests_and_list_of_all_blobs(dxf_base: DXFBase, docker_images: list[str]) -> tuple[list[Manifest], list[Blob]]:
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


def write_payload_descriptor_to_zip(zip_file: ZipFile, manifests: list[Manifest], manifests_paths: Iterator[str]):
    payload_descriptor = {}
    for manifest, manifest_path in zip(manifests, manifests_paths):
        payload_descriptor[manifest.docker_image_name] = manifest_path
    zip_file.writestr("payload_descriptor.json", json.dumps(payload_descriptor, indent=4))


def create_zip_from_docker_images(dxf_base: DXFBase, docker_images: list[str], zip_file: Path) -> None:
    with ZipFile(zip_file, "w") as zip_file:
        manifests, blobs_to_pull = get_manifests_and_list_of_all_blobs(dxf_base, docker_images)
        add_blobs_to_zip(dxf_base, zip_file, uniquify_blobs(blobs_to_pull))
        manifests_paths = add_manifests_to_zip(zip_file, manifests)
        write_payload_descriptor_to_zip(zip_file, manifests, manifests_paths)
