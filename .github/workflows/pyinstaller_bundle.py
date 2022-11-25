"""Run from the root of the repository"""

from pathlib import Path

from python_on_whales import docker


def repo_absolute_path():
    return str(Path(".").absolute())


def main():
    docker.run(
        "fydeinc/pyinstaller",
        ["docker_charon/__main__.py", "-n", "docker-charon"],
        volumes=[(repo_absolute_path(), "/src")],
        envs={"PLATFORMS": "linux"}
    )


if __name__ == "__main__":
    main()
