import yaml

with open('../os_info.yaml', 'r') as f:
    os_info = yaml.safe_load(f)

ssh_connections = 0
for os in os_info:
    for arch in os_info[os]['arch']:
        ssh_connections += 1

print(ssh_connections)
