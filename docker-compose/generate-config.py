#!/usr/bin/env python

# TODO vlad:
# - generate directly into docker-compose.yaml file
# - generate only 1 blank lines between block (not 2)

master_directories = [
    "autogen/aarch64-master-0",
    "autogen/amd64-master-0",
    "autogen/amd64-master-1",
    "autogen/ppc64le-master-0",
    "autogen/s390x-master-0",
    "autogen/x86-master-0",
    "master-docker-nonstandard",
    "master-galera",
    "master-libvirt",
    "master-nonlatent",
    "master-protected-branches",
]

docker_compose_template = """
  {master_name}:
    image: quay.io/mariadb-foundation/bb-master:master
    restart: unless-stopped
    container_name: {master_name}
    volumes:
      - ./logs:/var/log/buildbot
      - ./buildbot/:/srv/buildbot/master
    entrypoint:
      - /bin/bash
      - -c
      - "/srv/buildbot/master/docker-compose/start.sh {master_directory}"
    networks:
      net_front:
      net_back:
    ports:
      - "127.0.0.1:{port}:{port}"
    depends_on:
      - mariadb
      - crossbar
"""

# Generate startup scripts and Docker Compose pieces for each master directory
port = 8011
for master_directory in master_directories:
    master_name = master_directory.replace("/", "_")

    # Generate Docker Compose piece
    docker_compose_piece = docker_compose_template.format(
        master_name=master_name,
        master_directory=master_directory,
        port=port,
    )
    port += 1
    print(docker_compose_piece)
