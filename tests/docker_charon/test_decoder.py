from zipfile import ZipFile

import pytest
from python_on_whales import docker

from docker_charon import make_payload, push_payload_to_registry


@pytest.fixture
def add_destination_registry():
    destination_registry = docker.run(
        "registry:2",
        detach=True,
        publish=[(5001, 5000)],
        name="docker-charon-test-registry-destination",
    )
    yield
    print(docker.logs(destination_registry))
    docker.remove(destination_registry, force=True, volumes=True)


@pytest.mark.usefixtures("add_destination_registry")
def test_end_to_end_single_image(tmp_path):
    payload_path = tmp_path / "payload.json"
    make_payload(
        "localhost:5000", payload_path, ["ubuntu:bionic-20180125"], secure=False
    )

    push_payload_to_registry("localhost:5001", payload_path, secure=False)

    # we make sure the docker image exists in the registry and is working
    docker.image.remove("localhost:5001/ubuntu:bionic-20180125", force=True)
    assert (
        docker.run("localhost:5001/ubuntu:bionic-20180125", ["echo", "do"], remove=True)
        == "do"
    )


@pytest.mark.usefixtures("add_destination_registry")
def test_end_to_end_multiple_images(tmp_path):
    payload_path = tmp_path / "payload.json"
    make_payload(
        "localhost:5000",
        payload_path,
        ["ubuntu:bionic-20180125", "ubuntu:augmented"],
        secure=False,
    )

    push_payload_to_registry("localhost:5001", payload_path, secure=False)

    # we make sure the docker image exists in the registry and is working
    docker.image.remove("localhost:5001/ubuntu:bionic-20180125", force=True)
    assert (
        docker.run("localhost:5001/ubuntu:bionic-20180125", ["echo", "do"], remove=True)
        == "do"
    )

    docker.image.remove("localhost:5001/ubuntu:augmented", force=True)
    assert (
        docker.run(
            "localhost:5001/ubuntu:augmented", ["cat", "/hello-world.txt"], remove=True
        )
        == "hello-world"
    )


@pytest.mark.usefixtures("add_destination_registry")
def test_end_to_end_only_necessary_layers(tmp_path):
    payload_path = tmp_path / "payload.json"
    make_payload(
        "localhost:5000", payload_path, ["ubuntu:bionic-20180125"], secure=False
    )

    push_payload_to_registry("localhost:5001", payload_path, secure=False)

    # the bionic image is now in the registry. We can make a payload for the
    # augmented version, and it has a lot of layers in common
    payload_path.unlink()
    make_payload(
        "localhost:5000",
        payload_path,
        ["ubuntu:augmented"],
        docker_images_already_transferred=["ubuntu:bionic-20180125"],
        secure=False,
    )

    # we make sure that only two blobs are in the zip: the image configuration
    # and the layer that is common to both images
    all_blobs = []
    with ZipFile(payload_path) as zip_file:
        for name in zip_file.namelist():
            if name.startswith("blobs/"):
                all_blobs.append(name)
    assert len(all_blobs) == 2

    # we load the payload and make sure the augmented version is working
    push_payload_to_registry("localhost:5001", payload_path, secure=False)

    docker.image.remove("localhost:5001/ubuntu:augmented", force=True)
    assert (
        docker.run(
            "localhost:5001/ubuntu:augmented", ["cat", "/hello-world.txt"], remove=True
        )
        == "hello-world"
    )
