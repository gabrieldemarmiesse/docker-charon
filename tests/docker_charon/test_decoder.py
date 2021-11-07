from zipfile import ZipFile

import pytest
from python_on_whales import docker

import docker_charon
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

    images_pushed = push_payload_to_registry(
        "localhost:5001", payload_path, secure=False
    )
    assert images_pushed == ["ubuntu:bionic-20180125"]

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
    images_loaded = push_payload_to_registry(
        "localhost:5001", payload_path, secure=False
    )
    assert images_loaded == ["ubuntu:augmented"]

    docker.image.remove("localhost:5001/ubuntu:augmented", force=True)
    docker.image.remove("localhost:5001/ubuntu:bionic-20180125", force=True)
    assert (
        docker.run(
            "localhost:5001/ubuntu:augmented", ["cat", "/hello-world.txt"], remove=True
        )
        == "hello-world"
    )


@pytest.mark.usefixtures("add_destination_registry")
def test_image_skipped_is_still_declared_in_the_payload(tmp_path):
    payload_path = tmp_path / "payload.json"
    make_payload(
        "localhost:5000", payload_path, ["ubuntu:bionic-20180125"], secure=False
    )

    images_pushed = push_payload_to_registry(
        "localhost:5001", payload_path, secure=False
    )
    assert images_pushed == ["ubuntu:bionic-20180125"]

    payload_path.unlink()

    make_payload(
        "localhost:5000",
        payload_path,
        ["ubuntu:bionic-20180125", "ubuntu:augmented"],
        docker_images_already_transferred=["ubuntu:bionic-20180125"],
        secure=False,
    )

    images_pushed = push_payload_to_registry(
        "localhost:5001", payload_path, secure=False
    )
    assert set(images_pushed) == {"ubuntu:bionic-20180125", "ubuntu:augmented"}


@pytest.mark.usefixtures("add_destination_registry")
def test_raise_error_if_image_is_not_here_and_strict(tmp_path):
    payload_path = tmp_path / "payload.json"
    make_payload(
        "localhost:5000",
        payload_path,
        ["busybox:1.24.1", "ubuntu:augmented"],
        docker_images_already_transferred=["ubuntu:augmented"],
        secure=False,
    )

    with pytest.raises(docker_charon.ManifestNotFound) as err:
        push_payload_to_registry(
            "localhost:5001", payload_path, strict=True, secure=False
        )

    assert "ubuntu:augmented" in str(err.value)


@pytest.mark.usefixtures("add_destination_registry")
def test_warning_if_image_is_not_here(tmp_path):
    payload_path = tmp_path / "payload.json"
    make_payload(
        "localhost:5000",
        payload_path,
        ["busybox:1.24.1", "ubuntu:augmented"],
        docker_images_already_transferred=["ubuntu:augmented"],
        secure=False,
    )

    with pytest.warns(UserWarning) as record:
        push_payload_to_registry("localhost:5001", payload_path, secure=False)

    assert "ubuntu:augmented" in str(record[0].message)


@pytest.mark.usefixtures("add_destination_registry")
def test_mounting_layers_from_another_repository(tmp_path):
    payload_path = tmp_path / "payload.json"
    make_payload(
        "localhost:5000", payload_path, ["ubuntu:bionic-20180125"], secure=False
    )

    push_payload_to_registry("localhost:5001", payload_path, secure=False)

    # the bionic image is now in the registry. We can make a payload for the
    # augmented version, and it has a lot of layers in common
    # we use another repository, when decoding, layers should be transfered from
    # one repository to another
    payload_path.unlink()
    make_payload(
        "localhost:5000",
        payload_path,
        ["ubuntu-other:augmented"],
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
    images_loaded = push_payload_to_registry(
        "localhost:5001", payload_path, secure=False
    )
    assert images_loaded == ["ubuntu-other:augmented"]

    docker.image.remove("localhost:5001/ubuntu:augmented", force=True)
    docker.image.remove("localhost:5001/ubuntu-other:augmented", force=True)
    docker.image.remove("localhost:5001/ubuntu:bionic-20180125", force=True)
    assert (
        docker.run(
            "localhost:5001/ubuntu-other:augmented",
            ["cat", "/hello-world.txt"],
            remove=True,
        )
        == "hello-world"
    )
