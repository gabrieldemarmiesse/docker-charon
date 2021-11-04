# docker-charon

Transfer your Docker images to an air-gapped system efficiently

An air-gapped system is a system that is not connected to the internet.


### Why such a package?

It's a problem where a simple solution already exists. 
You can use the `docker save` and `docker load` commands to transfer your images to an air-gapped system with a tar.
This is actually what is recommended for simple use cases.

But let's say that you want to scale your deliveries, make regular updates, you'll soon 
notice issues with `docker save` and `docker load`:
* Speed when making the payload: The images must be pulled from the registry. Unpacked by the Docker engine, repacked again in a tar file. This is a LOT of disk access.
* Speed when loading the payload: The tar file is unpacked by the Docker engine. Then you can push the images to the registry. This involves a lot of unpacking and repacking of layers.
* Size of the payload.