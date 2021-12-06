import contextlib
import os
import subprocess
import sys
from zipfile import ZipFile

import pytest
from python_on_whales import docker

import docker_charon
from docker_charon import make_payload, push_payload
from docker_charon.common import PROJECT_ROOT


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
    payload_path = tmp_path / "payload.zip"
    make_payload(
        payload_path,
        ["ubuntu:bionic-20180125"],
        registry="localhost:5000",
        secure=False,
    )

    images_pushed = push_payload(payload_path, registry="localhost:5001", secure=False)
    assert images_pushed == ["ubuntu:bionic-20180125"]

    # we make sure the docker image exists in the registry and is working
    docker.image.remove("localhost:5001/ubuntu:bionic-20180125", force=True)
    assert (
        docker.run("localhost:5001/ubuntu:bionic-20180125", ["echo", "do"], remove=True)
        == "do"
    )


@pytest.mark.usefixtures("add_destination_registry")
def test_end_to_end_single_image_from_dockerhub(tmp_path):
    payload_path = tmp_path / "payload.zip"
    make_payload(payload_path, ["library/ubuntu:bionic-20180125"])

    images_pushed = push_payload(payload_path, registry="localhost:5001", secure=False)
    assert images_pushed == ["library/ubuntu:bionic-20180125"]

    # we make sure the docker image exists in the registry and is working
    docker.image.remove("localhost:5001/library/ubuntu:bionic-20180125", force=True)
    assert (
        docker.run(
            "localhost:5001/library/ubuntu:bionic-20180125", ["echo", "do"], remove=True
        )
        == "do"
    )


@pytest.mark.parametrize("method", ["direct", "with_cli_normal", "with_cli_stdout"])
@pytest.mark.usefixtures("add_destination_registry")
def test_end_to_end_multiple_images(tmp_path, method: str):
    payload_path = tmp_path / "payload.zip"
    if method == "with_cli_normal":
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "docker_charon",
                "make-payload",
                "--registry",
                "localhost:5000",
                "--insecure",
                "-f",
                str(payload_path),
                "ubuntu:bionic-20180125,ubuntu:augmented",
            ],
            stdout=sys.stderr,
            stderr=sys.stderr,
        )
    elif method == "with_cli_stdout":
        subprocess.check_call(
            [
                "bash",
                "-c",
                f"{sys.executable} -m docker_charon make-payload -r localhost:5000 --insecure ubuntu:bionic-20180125,ubuntu:augmented > {payload_path}",
            ],
        )
    else:
        make_payload(
            payload_path,
            ["ubuntu:bionic-20180125", "ubuntu:augmented"],
            registry="localhost:5000",
            secure=False,
        )

    if method == "with_cli_normal":
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "docker_charon",
                "push-payload",
                "--registry=localhost:5001",
                "--insecure",
                f"--file={payload_path}",
            ]
        )
    elif method == "with_cli_stdout":
        subprocess.check_call(
            [
                "bash",
                "-c",
                f"{sys.executable} -m docker_charon push-payload -r localhost:5001 --insecure < {payload_path}",
            ],
        )
    else:
        push_payload(payload_path, registry="localhost:5001", secure=False)

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


@pytest.mark.parametrize("use_cli", [True, False])
@pytest.mark.usefixtures("add_destination_registry")
def test_end_to_end_only_necessary_layers(tmp_path, use_cli: bool):
    payload_path = tmp_path / "payload.zip"
    make_payload(
        payload_path,
        ["ubuntu:bionic-20180125"],
        registry="localhost:5000",
        secure=False,
    )

    push_payload(payload_path, registry="localhost:5001", secure=False)

    # the bionic image is now in the registry. We can make a payload for the
    # augmented version, and it has a lot of layers in common
    payload_path.unlink()
    if use_cli:
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "docker_charon",
                "make-payload",
                "--already-transferred=ubuntu:bionic-20180125",
                "--insecure",
                "--registry=localhost:5000",
                "-f",
                str(payload_path),
                "ubuntu:augmented",
            ],
            stdout=sys.stderr,
            stderr=sys.stderr,
        )
    else:
        make_payload(
            payload_path,
            ["ubuntu:augmented"],
            docker_images_already_transferred=["ubuntu:bionic-20180125"],
            registry="localhost:5000",
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
    images_loaded = push_payload(payload_path, registry="localhost:5001", secure=False)
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
def test_end_to_end_only_necessary_layers_with_cli_and_stdin_stdout(tmp_path):
    payload_path = tmp_path / "payload.zip"
    subprocess.check_call(
        [
            "bash",
            "-c",
            f"{sys.executable} -m docker_charon make-payload -r localhost:5000 ubuntu:bionic-20180125 --insecure > {payload_path}",
        ]
    )
    images_pushed = subprocess.check_output(
        [
            "bash",
            "-c",
            f"{sys.executable} -m docker_charon push-payload -r localhost:5001 --insecure < {payload_path}",
        ]
    )
    assert images_pushed.decode() == "ubuntu:bionic-20180125\n"

    # the bionic image is now in the registry. We can make a payload for the
    # augmented version, and it has a lot of layers in common
    payload_path.unlink()
    subprocess.check_call(
        [
            "bash",
            "-c",
            (
                f"{sys.executable} -m docker_charon make-payload --already-transferred=ubuntu:bionic-20180125 "
                f" -r localhost:5000 ubuntu:augmented --insecure > {payload_path}"
            ),
        ]
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
    images_pushed = subprocess.check_output(
        [
            "bash",
            "-c",
            f"{sys.executable} -m docker_charon push-payload -r localhost:5001 --insecure < {payload_path}",
        ]
    )
    assert images_pushed.decode() == "ubuntu:augmented\n"

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
    payload_path = tmp_path / "payload.zip"
    make_payload(
        payload_path,
        ["ubuntu:bionic-20180125"],
        registry="localhost:5000",
        secure=False,
    )

    images_pushed = push_payload(payload_path, registry="localhost:5001", secure=False)
    assert images_pushed == ["ubuntu:bionic-20180125"]

    payload_path.unlink()

    make_payload(
        payload_path,
        ["ubuntu:bionic-20180125", "ubuntu:augmented"],
        docker_images_already_transferred=["ubuntu:bionic-20180125"],
        registry="localhost:5000",
        secure=False,
    )

    images_pushed = push_payload(payload_path, registry="localhost:5001", secure=False)
    assert set(images_pushed) == {"ubuntu:bionic-20180125", "ubuntu:augmented"}


@pytest.mark.usefixtures("add_destination_registry")
def test_raise_error_if_image_is_not_here_and_strict(tmp_path):
    payload_path = tmp_path / "payload.zip"
    make_payload(
        payload_path,
        ["busybox:1.24.1", "ubuntu:augmented"],
        docker_images_already_transferred=["ubuntu:augmented"],
        registry="localhost:5000",
        secure=False,
    )

    with pytest.raises(docker_charon.ManifestNotFound) as err:
        push_payload(payload_path, strict=True, registry="localhost:5001", secure=False)

    assert "ubuntu:augmented" in str(err.value)


@pytest.mark.usefixtures("add_destination_registry")
def test_warning_if_image_is_not_here(tmp_path):
    payload_path = tmp_path / "payload.zip"
    make_payload(
        payload_path,
        ["busybox:1.24.1", "ubuntu:augmented"],
        docker_images_already_transferred=["ubuntu:augmented"],
        registry="localhost:5000",
        secure=False,
    )

    with pytest.warns(UserWarning) as record:
        push_payload(payload_path, registry="localhost:5001", secure=False)

    assert "ubuntu:augmented" in str(record[0].message)


@pytest.mark.usefixtures("add_destination_registry")
def test_mounting_layers_from_another_repository(tmp_path):
    payload_path = tmp_path / "payload.zip"
    make_payload(
        payload_path,
        ["ubuntu:bionic-20180125"],
        registry="localhost:5000",
        secure=False,
    )

    push_payload(payload_path, registry="localhost:5001", secure=False)

    # the bionic image is now in the registry. We can make a payload for the
    # augmented version, and it has a lot of layers in common
    # we use another repository, when decoding, layers should be transfered from
    # one repository to another
    payload_path.unlink()
    make_payload(
        payload_path,
        ["ubuntu-other:augmented"],
        docker_images_already_transferred=["ubuntu:bionic-20180125"],
        registry="localhost:5000",
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
    images_loaded = push_payload(payload_path, registry="localhost:5001", secure=False)
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


@contextlib.contextmanager
def remember_cwd(new_directory):
    curdir = os.getcwd()
    os.chdir(new_directory)
    try:
        yield
    finally:
        os.chdir(curdir)


def test_create_docker_image():
    with remember_cwd(PROJECT_ROOT):
        docker.buildx.bake(load=True)
    docker.run("gabrieldemarmiesse/docker-charon:dev", ["--help"], remove=True)
    docker.run(
        "gabrieldemarmiesse/docker-charon:dev", ["make-payload", "--help"], remove=True
    )
    docker.run(
        "gabrieldemarmiesse/docker-charon:dev", ["push-payload", "--help"], remove=True
    )
