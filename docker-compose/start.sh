#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail
set -o posix

err() {
  echo >&2 "ERROR: $*"
  exit 1
}

# Make sure to pass the master name as the first argument
cd "/srv/buildbot/master/" || err "cd /srv/buildbot/master/"

# shellcheck disable=SC2226
[[ -f master-private.cfg ]] || ln -s ../master-private.cfg

VAR_DB_HOST=$(grep db_host master-private.cfg | awk '{print $3}' | sed s/\"//g)
echo "Waiting for MariaDB to start..."
while ! nc -z "$VAR_DB_HOST" 3306; do
  sleep 0.1
done
echo "MariaDB started"

echo "Waiting for Crossbar to start..."
while ! nc -z 127.0.0.1 8080; do
  sleep 0.1
done
echo "Crossbar started"

# ssh-key to connect to workers
if [[ $1 == "master-libvirt" ]]; then
  [[ -d /root/.ssh ]] || {
    mkdir /root/.ssh
    cp id_ed25519 /root/.ssh
    cp known_hosts /root/.ssh
  }
fi

# loop for debug
# while true; do date && sleep 30; done

exec buildbot start --nodaemon "$1"
