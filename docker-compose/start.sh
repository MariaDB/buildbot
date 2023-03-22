#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail
set -o posix

err() {
  echo_red >&2 "ERROR: $*"
  exit 1
}

cd /srv/buildbot/master || err "cd /srv/buildbot/master"
ln -sf /srv/buildbot-config/master-private.cfg master-private.cfg

cd "/srv/buildbot/master/"
# Generate master configs
/opt/buildbot/.venv/bin/python define_masters.py

# Make sure to pass the master name as the first argument
cd "/srv/buildbot/master/$1" || err "cd /srv/buildbot/master/$1"

echo "Waiting for MariaDB to start..."
while ! nc -z mariadb 3306; do
  sleep 0.1
done
echo "MariaDB started"

echo "Waiting for Crossbar to start..."
while ! nc -z crossbar 8080; do
  sleep 0.1
done
echo "Crossbar started"

buildbot start --nodaemon