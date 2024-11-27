#!/usr/bin/env python3
import argparse
import os

from dotenv import load_dotenv

config = {"private": {}}
exec(open("../master-private.cfg").read(), config, {})

MASTER_DIRECTORIES = [
    "master-nonlatent",
    "master-libvirt",
    "autogen/aarch64-master-0",
    "autogen/amd64-master-0",
    "autogen/amd64-master-1",
    "autogen/ppc64le-master-0",
    "autogen/s390x-master-0",
    "autogen/x86-master-0",
    "master-docker-nonstandard",
    "master-galera",
    "master-protected-branches",
    "master-docker-nonstandard-2",
    "master-bintars",
]

VOLUMES = ["./logs:/var/log/buildbot", "./buildbot/:/srv/buildbot/master"]

START_TEMPLATE = """
---
services:
  mariadb:
    image: mariadb:10.11
    restart: unless-stopped
    container_name: mariadb
    hostname: mariadb
    environment:
      - MARIADB_ROOT_PASSWORD=password
      - MARIADB_DATABASE=buildbot
      - MARIADB_USER=buildmaster
      - MARIADB_PASSWORD=password
      - MARIADB_AUTO_UPGRADE=1
    network_mode: host
    healthcheck:
      test: ['CMD', "mariadb-admin", "--password=password", "--protocol", "tcp", "ping"]
    volumes:
      - ./mariadb:/var/lib/mysql:rw
      - ./mariadb.cnf:/etc/mysql/conf.d/mariadb.cnf:ro
    logging:
      driver: journald
      options:
        tag: "bb-mariadb"

  crossbar:
    image: crossbario/crossbar
    restart: unless-stopped
    container_name: crossbar
    hostname: crossbar
    network_mode: host
    logging:
      driver: journald
      options:
        tag: "bb-crossbar"

  nginx:
    image: nginx:latest
    restart: unless-stopped
    container_name: nginx
    hostname: nginx
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d/:/etc/nginx/conf.d/
      - ./nginx/templates/:/etc/nginx/templates/:ro
      - /srv/buildbot/packages:/srv/buildbot/packages:ro
      - /srv/buildbot/galera_packages:/srv/buildbot/galera_packages:ro
      - /srv/buildbot/helper_files:/srv/buildbot/helper_files:ro
      - ./logs/nginx:/var/log/nginx
      - ./certbot/www/:/var/www/certbot/:ro
      - ./certbot/ssl/:/etc/nginx/ssl/:ro
    environment:
      - NGINX_ARTIFACTS_VHOST
      - NGINX_BUILDBOT_VHOST
    network_mode: host
    logging:
      driver: journald
      options:
        tag: "bb-nginx"

  master-web:
    image: quay.io/mariadb-foundation/bb-master:{environment}master-web
    restart: unless-stopped
    container_name: master-web
    hostname: master-web
    volumes:
      - ./logs:/var/log/buildbot
      - ./buildbot/:/srv/buildbot/master
    entrypoint:
      - /srv/buildbot/master/docker-compose/start-bbm-web.sh
    network_mode: host
    depends_on:
      mariadb:
        condition: service_healthy
      crossbar:
        condition: service_started
"""

DOCKER_COMPOSE_TEMPLATE = """
  {master_name}:
    image: quay.io/mariadb-foundation/bb-master:{environment}master
    restart: unless-stopped
    container_name: {master_name}
    hostname: {master_name}
    {volumes}
    entrypoint:
      - /bin/bash
      - -c
      - "/srv/buildbot/master/docker-compose/start.sh {master_directory}"
    network_mode: host
    depends_on:
      mariadb:
        condition: service_healthy
      crossbar:
        condition: service_started
"""


# Function to generate volumes section for Docker Compose
def generate_volumes(volumes, indent_level=2):
    indent = "   " * indent_level
    volume_lines = [f"{indent}- {volume}" for volume in volumes]
    return "volumes:\n{}".format("\n".join(volume_lines))


# Function to construct environment section for Docker Compose
def construct_env_section(env_vars):
    env_section = "    environment:\n"
    for key, value in sorted(env_vars.items()):
        if key.startswith("NGINX_"):
            continue
        elif key not in ["PORT", "MC_HOST_minio"]:
            env_section += f"      - {key}\n"
        else:
            env_section += f"      - {key}={value}\n"

    return env_section.rstrip("\n")


def main(args):
    # Load Volumes
    master_volumes = {
        key: VOLUMES[:]
        for key in [element.replace("/", "_") for element in MASTER_DIRECTORIES]
    }
    master_volumes["master-nonlatent"].append(
        "/srv/buildbot/packages:/srv/buildbot/packages"
    )  # Using FileUpload step

    # Capture the current environment variables' keys
    current_env_keys = set(os.environ.keys())

    # Load environment variables from the corresponding .env file
    env_file = ".env" if args.env == "prod" else ".env.dev"
    load_dotenv(env_file)

    # Determine the keys that were added by the .env file
    new_keys = set(os.environ.keys()) - current_env_keys

    # Extract only the variables from the .env file
    env_vars = {key: os.getenv(key) for key in new_keys}
    env_vars["PORT"] = "{port}"

    # Modify the start_template to include the environment variables for master-web
    start_template = START_TEMPLATE.replace(
        "container_name: master-web",
        f"container_name: master-web\n{construct_env_section(env_vars)}",
    )

    env_vars["MC_HOST_minio"] = "{mc_host}"
    # Modify the docker_compose_template to include the environment variables
    docker_compose_template = DOCKER_COMPOSE_TEMPLATE.replace(
        "container_name: {master_name}",
        f"container_name: {{master_name}}\n{construct_env_section(env_vars)}",
    )

    mc_host = config["private"]["minio_url"]
    starting_port = config["private"]["master-variables"]["starting_port"]
    master_web_port = 8010
    # Generate startup scripts and Docker Compose pieces for each master directory
    with open("docker-compose.yaml", mode="w", encoding="utf-8") as file:
        file.write(
            "# This is an autogenerated file. Do not edit it manually.\n\
# Use `python generate-config.py` instead."
        )
        file.write(
            start_template.format(
                port=master_web_port,
                cr_host_wg_addr=env_vars["CR_HOST_WG_ADDR"],
                environment="" if args.env == "prod" else "dev_",
            )
        )
        port = starting_port
        for master_directory in MASTER_DIRECTORIES:
            master_name = master_directory.replace("/", "_")

            # Generate Docker Compose piece
            docker_compose_piece = docker_compose_template.format(
                master_name=master_name,
                master_directory=master_directory,
                port=port,
                mc_host=mc_host,
                volumes=generate_volumes(master_volumes[master_name]),
                environment="" if args.env == "prod" else "dev_",
            )
            port += 1

            file.write(docker_compose_piece)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate Docker Compose configuration."
    )
    parser.add_argument(
        "--env",
        choices=["prod", "dev"],
        default="dev",
        help="Choose the environment (prod/dev). Default is dev.",
    )

    args = parser.parse_args()
    main(args)
