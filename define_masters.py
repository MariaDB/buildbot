#!/usr/bin/env python3

import os
import shutil
from collections import defaultdict

import yaml

BASE_PATH = "autogen/"
config = {"private": {}}
with open("master-private.cfg", "r") as file:
    exec(file.read(), config, {})

master_variables = config["private"]["master-variables"]

with open("os_info.yaml", encoding="utf-8") as file:
    OS_INFO = yaml.safe_load(file)

platforms = defaultdict(dict)

for os_name in OS_INFO:
    # TODO(cvicentiu) this should be removed, hack.
    if "install_only" in OS_INFO[os_name] and OS_INFO[os_name]["install_only"]:
        continue

    for arch in OS_INFO[os_name]["arch"]:
        builder_name = f"{arch}-{os_name}"
        platforms[arch][os_name] = {
            "image_tag": OS_INFO[os_name]["image_tag"],
            "tags": OS_INFO[os_name]["tags"],
        }

# Clear old configurations
if os.path.exists(BASE_PATH):
    shutil.rmtree(BASE_PATH)

for arch in platforms:
    # Create the directory for the architecture that is handled by each master
    # If for a given architecture there are more than "max_builds" builds,
    # create multiple masters
    # "max_builds" is defined is master-private.py
    num_masters = int(len(platforms[arch]) / master_variables["max_builds"]) + 1

    for master_id in range(num_masters):
        dir_path = f"{BASE_PATH}{arch}-master-{master_id}"
        os.makedirs(dir_path)

        master_config = {
            "builders": {arch: platforms[arch]},
            "workers": master_variables["workers"][arch],
            "log_name": f"master-docker-{arch}-{master_id}.log",
        }

        with open(f"{dir_path}/master-config.yaml", mode="w", encoding="utf-8") as file:
            yaml.dump(master_config, file)

        shutil.copyfile("master.cfg", dir_path + "/master.cfg")
        shutil.copyfile("master-private.cfg", dir_path + "/master-private.cfg")
        shutil.copyfile("buildbot.tac", dir_path + "/buildbot.tac")

    print(arch, len(master_config["builders"]))
