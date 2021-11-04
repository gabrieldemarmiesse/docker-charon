import pytest
from python_on_whales import docker

from docker_charon.common import PROJECT_ROOT


def transfer_to_base_registry(image_name):
    # we transfer the image to the local registry
    docker.pull(image_name)
    new_name = f"localhost:5000/{image_name}"
    docker.tag(image_name, new_name)
    docker.push(new_name)


@pytest.fixture(scope="session", autouse=True)
def initialize_local_registry():
    # we create a local registry and add a few docker images to it
    base_registry = docker.run(
        "registry:2",
        detach=True,
        publish=[(5000, 5000)],
        name="docker-charon-test-registry",
    )
    transfer_to_base_registry("ubuntu:bionic-20180125")

    docker.build(
        context_path=PROJECT_ROOT / "tests",
        file=PROJECT_ROOT / "tests" / "augmented-ubuntu.Dockerfile",
        tags=["localhost:5000/ubuntu:augmented"],
        push=True,
    )
    yield
    docker.remove(base_registry, force=True, volumes=True)
