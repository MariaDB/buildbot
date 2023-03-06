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

# config buildbot master-web
cd /srv/buildbot/master/master-web || err "cd"
for file in /srv/buildbot-config/master-web/*; do
  # shellcheck disable=SC2226
  ln -sf "$file"
done
# # loop for debug
# while true; do date && sleep 30; done

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
