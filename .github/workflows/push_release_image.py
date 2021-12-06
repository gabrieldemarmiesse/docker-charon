"""Run from the root of the repository"""
import os
from pathlib import Path

from python_on_whales import docker


def get_version() -> str:
    return Path("./VERSION.txt").read_text().strip()


def main():
    version = get_version()
    docker.login(
        username=os.environ["DOCKERHUB_USERNAME"],
        password=os.environ["DOCKERHUB_PASSWORD"],
    )
    docker.buildx.bake(["deploy-image"], push=True, variables={"TAG": version})


if __name__ == "__main__":
    main()
