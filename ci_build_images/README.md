# Dockerfiles for BB workers

## manually build containers

Command line example to manually build containers:

```console
# debian
cat debian.Dockerfile buildbot-worker.Dockerfile >Dockerfile
docker build . -t mariadb.org/buildbot/debian:sid --build-arg MARIADB_BRANCH=11.1 --build-arg BASE_IMAGE=debian:sid
# ubuntu
cat debian.Dockerfile buildbot-worker.Dockerfile >Dockerfile
docker build . -t mariadb.org/buildbot/ubuntu:22.04 --build-arg MARIADB_BRANCH=11.1 --build-arg BASE_IMAGE=ubuntu:22.04
# fedora
cat fedora.Dockerfile buildbot-worker.Dockerfile >Dockerfile
docker build . -t mariadb.org/buildbot/fedora:39 --build-arg BASE_IMAGE=fedora:39
# almalinux9
cat centos.Dockerfile pip.Dockerfile common.Dockerfile >Dockerfile
docker build . -t mariadb.org/buildbot/almalinux:9 --build-arg BASE_IMAGE=almalinux:9
# rockylinux9
cat centos.Dockerfile pip.Dockerfile common.Dockerfile >Dockerfile
docker build . -t mariadb.org/buildbot/rockylinux:9 --build-arg BASE_IMAGE=rockylinux:9
# rhel9
cat rhel.Dockerfile qpress.Dockerfile buildbot-worker.Dockerfile >Dockerfile
echo "12345_KEYNAME" >rhel_keyname
echo "12345_ORGID" >rhel_orgid
docker build . -t mariadb.org/buildbot/rhel:9 --build-arg "BASE_IMAGE=ubi9" --secret id=rhel_orgid,src=./rhel_orgid --secret id=rhel_keyname,src=./rhel_keyname
```

## search for missing dependencies

apt:

```bash
for pkg in $(cat list.txt); do echo -e "\n$pkg: $(dpkg -l | grep "$pkg")"; done
```

rpm:

```bash
for pkg in $(cat list.txt); do echo -e "\n$pkg: $(rpm -qa | grep "$pkg")"; done
```

## Best practice

### Sort and remove duplicate packages

One package by line, see:
<https://docs.docker.com/develop/develop-images/dockerfile_best-practices/#sort-multi-line-arguments>

Use the following in vim:

```vim
:sort u
```

### Use hadolint tool to verify the dockerfile

```console
docker run -i -v $(pwd):/mnt -w /mnt hadolint/hadolint:latest hadolint /mnt/fedora.Dockerfile
```
