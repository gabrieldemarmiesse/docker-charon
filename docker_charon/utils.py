from __future__ import annotations

import json
from enum import Enum
from typing import IO, Iterator, Optional

from dxf import DXF, DXFBase


class PayloadSide(Enum):
    ENCODER = "ENCODER"
    DECODER = "DECODER"


class Blob:
    def __init__(self, dxf_base: DXFBase, digest: str, repository: str):
        self.dxf_base = dxf_base
        self.digest = digest
        self.repository = repository

    def __repr__(self):
        return f"{self.repository}/{self.digest}"

    def __eq__(self, other: Blob):
        return self.digest == other.digest and self.repository == other.repository


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


def progress_as_string(index: int, container: list) -> str:
    return f"[{index+1}/{len(container)}]"


def file_to_generator(file_like: IO) -> Iterator[bytes]:
    while True:
        chunk = file_like.read(2 ** 15)
        if not chunk:
            break
        yield chunk
