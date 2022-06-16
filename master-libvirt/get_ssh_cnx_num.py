""" Get ssh connexions for Buildbot master libvirt
watchdog script"""
import yaml

with open('../os_info.yaml', 'r') as f:
    os_info = yaml.safe_load(f)

SSH_CONNECTIONS = 0
for os in os_info:
    for arch in os_info[os]['arch']:
        SSH_CONNECTIONS += 1

print(SSH_CONNECTIONS)
