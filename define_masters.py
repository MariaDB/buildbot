#!/usr/bin/env python3

import os
import shutil

import yaml

BASE_PATH = "autogen/"
config = {"private": {}}
exec(open("master-private.cfg").read(), config, {})

with open("os_info.yaml", encoding="utf-8") as file:
    os_info = yaml.safe_load(file)

platforms = {}

for os_name in os_info:
    if "install_only" in os_info[os_name] and os_info[os_name]["install_only"]:
        continue
    for arch in os_info[os_name]["arch"]:
        builder_name = arch + "-" + os_name
        if arch not in platforms:
            platforms[arch] = []
        platforms[arch].append({
            os_name: {
                'image_tag': os_info[os_name]['image_tag'],
                # TODO(cvicentiu) load tags from os_info.
                'tags': ['autobake', 'release_packages', 'bleeding_edge']
            }
        })

# Clear old configurations
if os.path.exists(BASE_PATH):
    shutil.rmtree(BASE_PATH)

idx = 0
for arch in platforms:
    master_variables = config["private"]["master-variables"]
    # Create the directory for the architecture that is handled by each master
    # If for a given architecture there are more than "max_builds" builds,
    # create multiple masters
    # "max_builds" is defined is master-private.py
    num_masters = (
        int(len(platforms[arch]) / master_variables["max_builds"]) + 1
    )

    for master_id in range(num_masters):
        dir_path = f'{BASE_PATH}{arch}-master-{master_id}'
        os.makedirs(dir_path)

        master_config = {
            'builders': {arch: platforms[arch]},
            'workers': master_variables["workers"][arch],
            'port': master_variables["starting_port"] + idx,
            'log_name': f'master-docker-{arch}-{master_id}.log'

        }
        with open(f"{dir_path}/master-config.yaml", mode="w",
                  encoding="utf-8") as file:
            yaml.dump(master_config, file)

        shutil.copyfile("master.cfg", dir_path + "/master.cfg")
        shutil.copyfile("master-private.cfg", dir_path + "/master-private.cfg")

        # TODO(cvicentiu) fix this through environment variables, not this
        # weird hardcoding and code generation.
        buildbot_tac = (
            open("buildbot.tac", encoding="utf-8").read() % master_config["log_name"]
        )
        with open(dir_path + "/buildbot.tac", mode="w", encoding="utf-8") as f:
            f.write(buildbot_tac)
        idx += 1
    print(arch, len(master_config["builders"]))
