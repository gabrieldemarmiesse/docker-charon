from pathlib import Path

from setuptools import find_packages, setup

CURRENT_DIR = Path(__file__).parent


def get_long_description() -> str:
    return (CURRENT_DIR / "README.md").read_text(encoding="utf8")


setup(
    name="docker-charon",
    version=(CURRENT_DIR / "VERSION.txt").read_text(encoding="utf8").strip(),
    description="A tool to move your Docker images to an air-gapped registry.",
    install_requires=(CURRENT_DIR / "requirements.txt").read_text().splitlines(),
    packages=find_packages(),
    include_package_data=True,  # will read the MANIFEST.in
    license="MIT",
    python_requires=">=3.8, <4",
    entry_points={
        "console_scripts": ["docker-charon=docker_charon.__main__:main"],
    },
)
