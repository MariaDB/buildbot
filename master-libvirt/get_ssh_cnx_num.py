""" Get ssh connexions for Buildbot master libvirt
watchdog script"""

import yaml

with open("../os_info.yaml") as f:
    os_info = yaml.safe_load(f)

SSH_CONNECTIONS = 0
for os in os_info:
    for arch in os_info[os]["arch"]:
        if (
            arch not in ["s390x", "x86"]
            and "sles" not in os
        ):
            SSH_CONNECTIONS += 1

print(SSH_CONNECTIONS)
