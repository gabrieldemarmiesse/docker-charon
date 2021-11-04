import json

from dxf import DXFBase

from docker_charon.encoder import (
    get_manifest_and_list_of_blobs_to_pull,
    make_payload,
    uniquify_blobs,
)


def test_get_manifest_and_list_of_all_blobs():
    dxf_base = DXFBase("localhost:5000", secure=False)

    manifest, blobs = get_manifest_and_list_of_blobs_to_pull(
        dxf_base, "ubuntu:bionic-20180125"
    )
    assert json.loads(manifest.content) == {
        "schemaVersion": 2,
        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
        "config": {
            "mediaType": "application/vnd.docker.container.image.v1+json",
            "size": 3615,
            "digest": "sha256:08c67959b9793ec58cd67e96fd7f55a21b294dbcb74e4f32b79a6f577a66ab43",
        },
        "layers": [
            {
                "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
                "size": 31835301,
                "digest": "sha256:fe2aebf5d506a25f30f34d42fbd8e3eb456d9b5be93bfc5a36e4710416692370",
            },
            {
                "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
                "size": 839,
                "digest": "sha256:092d9419b898db967082b545be925694041a80c77cef75e80f6d22a2117eaa4d",
            },
            {
                "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
                "size": 398,
                "digest": "sha256:55b1a71b0f4c9f395b8b9a80c089b0d3b4afce7aa7b4a5ed821ffb1f1c492dd5",
            },
            {
                "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
                "size": 850,
                "digest": "sha256:65e00a3d2e0f4f7ae7407e7ef74e9ec26e6c850eb9529a69c04080db5244024b",
            },
            {
                "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
                "size": 162,
                "digest": "sha256:b87e7aec96844ed589fa43774e80667815fdb5f5cd0df486afb56fe464dc2751",
            },
        ],
    }

    assert len(blobs) == 6
    for blob in blobs:
        assert blob.repository == "ubuntu"
        assert blob.digest in manifest.content

    assert len(uniquify_blobs(blobs)) == len(blobs)


def test_make_payload_from_path(tmp_path):
    zip_path = tmp_path / "test.zip"

    make_payload("localhost:5000", zip_path, ["ubuntu:bionic-20180125"], secure=False)


def test_make_payload_from_str(tmp_path):
    zip_path = tmp_path / "test.zip"

    make_payload(
        "localhost:5000", str(zip_path), ["ubuntu:bionic-20180125"], secure=False
    )


def test_make_payload_from_opened_file(tmp_path):
    zip_path = tmp_path / "test.zip"
    with open(zip_path, "wb") as f:
        make_payload("localhost:5000", f, ["ubuntu:bionic-20180125"], secure=False)
