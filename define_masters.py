import yaml
import os
import shutil

base_path = "autogen/"
config = { "private": { } }
exec(open("master-private.cfg").read(), config, { })

with open('os_info.yaml', 'r') as f:
    os_info = yaml.safe_load(f)

platforms = {}

for os_name in os_info:
    for arch in os_info[os_name]['arch']:
        builder_name = arch + '-' + os_name
        if arch not in platforms:
            platforms[arch] = []
        platforms[arch].append(builder_name)

# Clear old configurations
if os.path.exists(base_path):
    shutil.rmtree(base_path)

idx = 0
for arch in platforms:
    # Create the directory for the architecture that is handled by each master
    # If for a given architecture there are more than "max_builds" builds,
    # create multiple masters
    # "max_builds" is defined is master-private.py
    num_masters = int(len(platforms[arch]) / config['private']['master-variables']['max_builds']) + 1

    for master_id in range(num_masters):
        dir_path = base_path + arch + "-master-" + str(master_id)
        os.makedirs(dir_path)

        master_config = {}
        master_config['builders'] = platforms[arch]
        master_config['workers'] = config['private']['master-variables']['workers'][arch]
        master_config['port'] = config['private']['master-variables']['starting_port'] + idx
        master_config['log_name'] = "master-docker-" + arch + "-" + str(master_id) + '.log'

        with open(dir_path + '/master-config.yaml', 'w') as f:
            yaml.dump(master_config, f)

        shutil.copyfile('master.cfg', dir_path + '/master.cfg')
        shutil.copyfile('master-private.cfg', dir_path + '/master-private.cfg')

        buildbot_tac = open("buildbot.tac", "r").read() % master_config['log_name']
        with open(dir_path + '/buildbot.tac', 'w') as f:
            f.write(buildbot_tac)
        idx += 1
    print(arch, len(master_config['builders']))
 
