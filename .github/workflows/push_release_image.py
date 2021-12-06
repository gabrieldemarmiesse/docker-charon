import os
from pathlib import Path

from python_on_whales import docker

PROJECT_ROOT = Path(__file__).parents[2]


def get_version() -> str:
    return (PROJECT_ROOT / "VERSION.txt").read_text().strip()


def main():
    version = get_version()
    os.chdir(PROJECT_ROOT)
    docker.login(
        username=os.environ["DOCKERHUB_USERNAME"],
        password=os.environ["DOCKERHUB_PASSWORD"],
    )
    docker.buildx.bake(["deploy-image"], push=True, variables={"TAG": version})
