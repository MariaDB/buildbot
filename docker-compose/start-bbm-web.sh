#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail
set -o posix

err() {
  echo >&2 "ERROR: $*"
  exit 1
}

echo "Waiting for MariaDB to start..."
while ! nc -z mariadb 3306; do
  sleep 0.1
done
echo "MariaDB started"

echo "Waiting for Crossbar to start..."
while ! nc -z crossbar 8080; do
  sleep 0.1
done
echo "MariaDB started"

# # loop for debug
# while true; do date && sleep 30; done

cd /srv/buildbot/master/master-web || err "cd /srv/buildbot/master/master-web"
# shellcheck disable=SC2226
[[ -f master-private.cfg ]] || ln -s ../master-private.cfg
buildbot upgrade-master /srv/buildbot/master/master-web
buildbot start --nodaemon
