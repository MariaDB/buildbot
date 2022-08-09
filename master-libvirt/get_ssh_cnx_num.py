""" Get ssh connexions for Buildbot master libvirt
watchdog script"""
import yaml

with open('../os_info.yaml', 'r') as f:
    os_info = yaml.safe_load(f)

SSH_CONNECTIONS = 0
for os in os_info:
    for arch in os_info[os]['arch']:
        addInstall = True
        if 'has_install' in os_info[os]:
            addInstall = os_info[os]['has_install']
        if arch not in ['s390x', 'x86'] and addInstall:
            SSH_CONNECTIONS += 1

print(SSH_CONNECTIONS)
