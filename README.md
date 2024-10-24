# docker-charon


**Note: This project is no longer maintained. Users can still install the latest version (0.4.3) but 
if someone wishes to have something fixed/changed, then this user should fork the project.
If someone wishes to continue to maintain the project, feel free to publish it on Pypi under the name
docker-charon-2 or something similar.**

Transfer your Docker images to an air-gapped system efficiently. 

(An air-gapped system is a system that is not connected to the internet)

![](https://github.com/gabrieldemarmiesse/docker-charon/blob/cbf5e2a6f50152c6754000ae8c0551c884450f15/images/logo.jpg)


From wikipedia:

> In Greek mythology, Charon or Kharon (/ˈkɛərɒn, -ən/; Ancient Greek: Χάρων) is a 
> psychopomp, the ferryman of Hades who carries souls of the newly deceased 
> who had received the rites of burial, across the river Acheron 
> (or in some later accounts, across the river Styx) that 
> divided the world of the living from the world of the dead.

## Installation
```bash
pip install docker-charon
```

You don't need Docker installed locally to run this tool.

## Example

You can run those examples directly from the command line. Here we use docker, but it's only for demonstration purposes.
In a real world scenario, you don't need Docker at all. Just two registries.

#### Use as a command line

```bash
pip install docker-charon

# we setup a local registry and will pretend it's air-gapped
# we'll transfer docker images from dockerhub to our local registry
docker run -d -p 5000:5000 --restart=always --name registry registry:2


docker-charon make-payload -f ./payload.zip python:3.9.2-alpine,elasticsearch:7.14.1
docker-charon push-payload -f ./payload.zip --insecure --registry=localhost:5000

# our images are now in the air-gapped registry
# you can verify it with 
docker pull localhost:5000/python:3.9.2-alpine

# now let's upgrade images in our local registry without taking the layers that are already there
# we take higher versions, python:3.9.2 -> python:3.9.3 for example

docker-charon make-payload -f ./payload2.zip --already-transferred=python:3.9.2-alpine,elasticsearch:7.14.1 python:3.9.3-alpine,elasticsearch:7.14.2
# you'll see that some layers are skipped because they are already in the registry
# the outputs will be something like this for those layers:
# Skipping elasticsearch/sha256:7a0437... because it's already in the destination registry in the repository elasticsearch
# the argument --already-transferred is the one that does the magic

docker-charon push-payload -f ./payload2.zip --insecure --registry=localhost:5000 
# you can verify it with 
docker pull localhost:5000/python:3.9.3-alpine
```

#### Use as a python library

```bash
pip install docker-charon

# we setup a local registry and will pretend it's air-gapped
# we'll transfer docker images from dockerhub to our local registry
docker run -d -p 5000:5000 --restart=always --name registry registry:2
```


```python
from docker_charon import make_payload, push_payload

make_payload("./payload.zip", ["python:3.9.2-alpine", "elasticsearch:7.14.1"])
push_payload("./payload.zip", secure=False, registry="localhost:5000")

# our images are now in the air-gapped registry
# you can verify it with 
# docker pull localhost:5000/python:3.9.2-alpine

# now let's upgrade images in our local registry without taking the layers that are already there
# we take higher versions, python:3.9.2 -> python:3.9.3 for example
make_payload(
    "./payload2.zip", 
    ["python:3.9.3-alpine", "elasticsearch:7.14.2"], 
    docker_images_already_transferred=["python:3.9.2-alpine", "elasticsearch:7.14.1"]
)
# you'll see that some layers are skipped because they are already in the registry
# the outputs will be something like this for those layers:
# Skipping elasticsearch/sha256:7a0437... because it's already in the destination registry in the repository elasticsearch
# the argument docker_images_already_transferred is the one that does the magic
push_payload("./payload2.zip", secure=False, registry="localhost:5000")

# you can verify it with 
# docker pull localhost:5000/python:3.9.3-alpine
```


#### Use as a docker image

It has the same command line interface as the command line version, but we'll use stdin/stdout instead of `-f` to 
avoid using docker volumes.

```bash
# we setup a local registry and will pretend it's air-gapped
# we'll transfer docker images from dockerhub to our local registry
docker run -d -p 5000:5000 --restart=always --name registry registry:2

docker run gabrieldemarmiesse/docker-charon make-payload python:3.9.2-alpine,elasticsearch:7.14.1 > ./payload.zip
# here we use the -i argument of docker run to read from stdin (by default stdin is not available in docker)
# we also use --net=host to be able to communicate with localhost:5000
docker run -i --net=host gabrieldemarmiesse/docker-charon push-payload --insecure --registry=localhost:5000 < ./payload.zip

# our images are now in the air-gapped registry
# you can verify it with 
docker pull localhost:5000/python:3.9.2-alpine

# now let's upgrade images in our local registry without taking the layers that are already there
# we take higher versions, python:3.9.2 -> python:3.9.3 for example

docker run gabrieldemarmiesse/docker-charon make-payload --already-transferred=python:3.9.2-alpine,elasticsearch:7.14.1 python:3.9.3-alpine,elasticsearch:7.14.2 > ./payload2.zip
# you'll see that some layers are skipped because they are already in the registry
# the outputs will be something like this for those layers:
# Skipping elasticsearch/sha256:7a0437... because it's already in the destination registry in the repository elasticsearch
# the argument --already-transferred is the one that does the magic

docker run  -i --net=host gabrieldemarmiesse/docker-charon push-payload --insecure --registry=localhost:5000 < ./payload2.zip
# you can verify it with 
docker pull localhost:5000/python:3.9.3-alpine
```

## Arguments

#### Command line and Docker image

**docker-charon make-payload**
```
$ docker-charon make-payload --help
Usage: docker-charon make-payload [OPTIONS] DOCKER_IMAGES_TO_TRANSFER

  Create a payload (.zip file) with docker images inside. This zip file can
  then be unpacked into a registry in another system.

  By providing images that were already transferred to the new registry, you
  can reduce the size and creation time of the payload. This is because
  docker-charon only takes the layers that were not already transferred.

  The payload is written to stdout by default. You can provide a file path
  to write the payload to by using the --file (or -f) option.

Arguments:
  DOCKER_IMAGES_TO_TRANSFER  docker images to transfer, a commas delimited
                             list of docker image names. Do not include the
                             registry name.  [required]


Options:
  -a, --already-transferred TEXT  docker images already present in the remote
                                  registry, a commas delimited list of docker
                                  image names. Do not include the registry
                                  name.

  -f, --file TEXT                 Where to write the payload zip file. If this
                                  is not provided, the payload will be written
                                  to stdout.

  -r, --registry TEXT             The registry to push the payload to. It
                                  defaults to dockerhub (registry-1.docker.io)

  -i, --insecure                  Use --insecure if the registry uses http
                                  instead of https

  -u, --username TEXT             The username to use to connect to the
                                  registry. If you want more security and
                                  don't want your username to appear in your
                                  shell history, you can also use the
                                  environment variable DOCKER_CHARON_USERNAME

  -p, --password TEXT             The password to use to connect to the
                                  registry. If you want more security and
                                  don't want your password to appear in your
                                  shell history, you can also use the
                                  environment variable DOCKER_CHARON_PASSWORD
```

**docker-charon push-payload**

```
$ docker-charon push-payload --help
Usage: docker-charon push-payload [OPTIONS]

  Unpack the payload (.zip file) into a docker registry.

  The zip file must have been created by 'docker-charon make-payload ...'

  This command will output to stdout the list of images that were
  transferred. One image per line.

  By default, the payload is read from stdin. You can provide a file path to
  read the payload from by using the --file (or -f) option.

Options:
  -f, --file TEXT      The payload zip file. If this is not provided, the
                       payload will be read from stdin.

  -s, --strict         Fails if there is a mismatch between what was given
                       with --already-transferred and what is in the registry.
                       [default: False]

  -r, --registry TEXT  The registry to push the payload to. It defaults to
                       dockerhub (registry-1.docker.io)  [default:
                       registry-1.docker.io]

  -i, --insecure       Use --insecure if the registry uses http instead of
                       https

  -u, --username TEXT  The username to use to connect to the registry. If you
                       want more security and don't want your username to
                       appear in your shell history, you can also use the
                       environment variable DOCKER_CHARON_USERNAME

  -p, --password TEXT  The password to use to connect to the registry. If you
                       want more security and don't want your password to
                       appear in your shell history, you can also use the
                       environment variable DOCKER_CHARON_PASSWORD
```


#### Python library

**make_payload**

Creates a payload from a list of docker images

All the docker images must be in the same registry.
This is currently a limitation of the docker-charon package.

If you are interested in multi-registries, please open an issue.

**Arguments**

- **zip_file**: The path to the zip file to create. It can be a `pathlib.Path` or
    a `str`. It's also possible to pass a file-like object. The payload with
    all the docker images is a single zip file.
- **docker_images_to_transfer**: The list of docker images to transfer. Do not include
    the registry name in the image name.
- **docker_images_already_transferred**: The list of docker images that have already
    been transferred to the air-gapped registry. Do not include the registry
    name in the image name. It's optional but if you use it, you can make the 
    payload a lot smaller.
- **registry**: The registry to pull the images from. The name of the registry
    must not be included in `docker_images_to_transfer` and
    `docker_images_already_transferred`. Defaults to dockerhub (`registry-1.docker.io`).
- **secure**: Set to `False` if the registry doesn't support HTTPS (TLS). Default
    is `True`.
- **username**: The username to use for authentication to the registry. Optional if
    the registry doesn't require authentication.
- **password**: The password to use for authentication to the registry. Optional if
    the registry doesn't require authentication.


**push_payload**

Push the payload to the registry.

It will iterate over the docker images and push the blobs and the manifests.

**Arguments**

- **zip_file**: the zip file containing the payload. It can be a `pathlib.Path`, a `str`
    or a file-like object.
- **strict**: `False` by default. If True, it will raise an error if the 
     some blobs/images are missing.
     That can happen if the user set an image in `docker_images_already_transferred`
     that is not in the registry.
- **registry**: The registry to push the images to. Defaults to dockerhub (`registry-1.docker.io`).
- **secure**: whether to use TLS (HTTPS) or not to connect to the registry,
    default is `True`.
- **username**: the username to use to connect to the registry. Optional
    if the registry does not require authentication.
- **password**: the password to use to connect to the registry. Optional
    if the registry does not require authentication.

**Returns**

The list of docker images loaded in the registry.

It also includes the list of docker images that were already present
in the registry and were not included in the payload to optimize the size.
In other words, it's the argument `docker_images_to_transfer` that you passed
to the function `docker_charon.make_payload(...)`.


## Why such a package?

#### The usual method: docker save and load

It's a problem where a simple solution already exists. 
You can use the `docker save` and `docker load` commands to transfer your images to an air-gapped system with a tar.
This is actually what is recommended for simple use cases.

Here is the recap of the `docker pull -> docker save -> docker load -> docker push` method:

![](https://github.com/termim/docker-charon/blob/a2a499a715f42947fb940bc4a808b23c316994d4/images/with_docker_save_load.png)


But let's say that you want to scale your deliveries, make regular updates, you'll soon 
notice issues with `docker save` and `docker load`:
* Speed when making the payload: The images must be pulled from the registry. Unpacked by the Docker engine, repacked again in a tar file. This is a LOT of disk access.
* Speed when loading the payload: The tar file is unpacked by the Docker engine. Then you can push the images to the registry. This involves a lot of unpacking and repacking of layers.
* Size of the payload. `docker save` take all the layers and images you declare. 
    Even if some images and layers are already present in the air-gapped system.

#### The docker-charon method:

Docker-charon is a package that addresses these issues. 

It reads the registry directly to make the payload.
You don't even need docker on the machine making the payload and the machine loading the payload.

It can also compute the diff in a smart way if you provide the images already present in the 
air-gapped system registry. That means much smaller payloads because some layers are not 
transferred a second time.

Here is the recap of the docker-charon method:

![](https://github.com/termim/docker-charon/blob/a2a499a715f42947fb940bc4a808b23c316994d4/images/with_docker_charon.png)


### How does it work?

docker-charon will query the registry, get the manifests of the docker images,
and then will only download the blobs that were not transferred yet to the 
air-gapped registry.

Everything is put in a single zip. Zip files are a good choice because it's 
possible to randomly access files within it and then decompress them in 
whatever order is needed.

When in the air-gapped system, the `push_payload` function will
read the zip file index and push the blobs and the manifests to the registry on the fly.

The Docker images are then ready to be pulled in your air-gapped cluster!
