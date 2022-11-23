#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail
set -o posix

err() {
  echo_red >&2 "ERROR: $*"
  exit 1
}

[[ -d /srv/buildbot ]] || mkdir -p /srv/buildbot
[[ -d /srv/buildbot/master ]] ||
  git clone https://github.com/MariaDB/buildbot/ /srv/buildbot/master

cd /srv/buildbot/master || err "cd /srv/buildbot/master"

[[ -f /srv/buildbot/master/master-private.cfg ]] || {
  for file in *-sample; do
    ln -s "$file" "${file/-sample/}"
  done
}

# connection to the DB
sed -i 's/localhost/mariadb/' master-private.cfg

echo "Waiting for MariaDB to start..."
while ! nc -z mariadb 3306; do
  sleep 0.1
done
echo "MariaDB started"

# start buildbot master
cd /srv/buildbot/master/master-web || err "cd /srv/buildbot/master/master-web"
sed -i 's#https://buildbot.mariadb.org#http://localhost#' master.cfg
[[ -f master-private.cfg ]] || ln -s ../master-private.cfg master-private.cfg

# # loop for debug
# while true; do date && sleep 30; done

buildbot upgrade-master /srv/buildbot/master/master-web
buildbot start --nodaemon
