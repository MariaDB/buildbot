#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail
set -o posix

err() {
  echo >&2 "ERROR: $*"
  exit 1
}

usage() {
  echo "Usage: $0 -e <DEV|PROD>"
  exit 0
}

ENVIRONMENT=""

while getopts ":e:" opt; do
  case ${opt} in
    e )
      ENVIRONMENT=$OPTARG
      ;;
    \? )
      usage
      ;;
    : )
      usage
      ;;
  esac
done

if [[ -z "$ENVIRONMENT" ]]; then
  usage
fi

case $ENVIRONMENT in
  DEV)
    IMAGE="quay.io/mariadb-foundation/bb-master:dev_master"
    ENVFILE="docker-compose/.env.dev"
    ;;
  PROD)
    IMAGE="quay.io/mariadb-foundation/bb-master:master"
    ENVFILE="docker-compose/.env"
    ;;
  *)
    err "Unknown environment: $ENVIRONMENT. Use DEV or PROD."
    ;;
esac

mkdir -p master-credential-provider
[[ -f master-private.cfg ]] ||
  ln -s master-private.cfg-sample master-private.cfg
[[ -f master-config.yaml ]] ||
  ln -s master-config.yaml-sample master-config.yaml

if command -v podman >/dev/null; then
  RUNC=podman
else
  if command -v docker >/dev/null; then
    RUNC=docker
  else
    err "need a container system (docker/podman)"
  fi
fi

command -v python3 >/dev/null ||
  err "python3 command not found"

python3 define_masters.py
echo "Checking master.cfg"
# Port is set by generate-config.py (docker-compose), not present in .env
$RUNC run -i -v "$(pwd):/srv/buildbot/master" \
  --env PORT=1234 \
  --env-file <(sed "s/='\([^']*\)'/=\1/" $ENVFILE) \
  -w /srv/buildbot/master \
  $IMAGE \
  buildbot checkconfig master.cfg
echo -e "done\n"
# not checking libvirt config file (//TEMP we need to find a solution
# to not check ssh connection)
for dir in autogen/* \
  master-bintars \
  master-docker-nonstandard \
  master-docker-nonstandard-2 \
  master-galera \
  master-nonlatent \
  master-protected-branches \
  master-web; do
  echo "Checking $dir/master.cfg"
  $RUNC run -i -v "$(pwd):/srv/buildbot/master" \
    --env PORT=1234 \
    --env-file <(sed "s/='\([^']*\)'/=\1/" $ENVFILE) \
    -w "/srv/buildbot/master/$dir" \
    $IMAGE \
    buildbot checkconfig master.cfg
  echo -e "done\n"
done