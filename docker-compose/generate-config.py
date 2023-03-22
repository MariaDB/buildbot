import os

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
    volumes:
      - ./logs:/var/log/buildbot
      - ./config:/srv/buildbot-config
      - ./start.sh:/usr/local/bin/start.sh
      - ./buildbot/:/srv/buildbot/master
    entrypoint:
      - /bin/bash
      - -c
      - "/usr/local/bin/start.sh {master_directory}"
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
