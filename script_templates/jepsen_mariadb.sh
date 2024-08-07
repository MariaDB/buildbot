#!/usr/bin/env bash

set -ex

err() {
  echo >&2 "ERROR: $*"
  exit 1
}

NPROC="%(prop:jobs)s"

LEIN_OPTIONS=(
  "run"
  "test"
  "--db" "maria-docker"
  "--nodes" "localhost"
  "--concurrency" "${NPROC}"
  "--rate" "1000"
  "--time-limit" "60"
  "--key-count" "40"
  "--no-ssh=true"
  "--innodb-strict-isolation=true"
  "--mariadb-install-dir=/home/buildbot/mariadb-bin"
)

cd ../jepsen-mariadb ||
  err "cd ../jepsen-mariadb"

log_lines() {
  msg="$1"
  line="${msg//?/=}"
  echo -e "\n${line}\n${msg}\n${line}\n"
}
log_lines "Append serializable"
../lein "${LEIN_OPTIONS[@]}" -w append -i serializable

log_lines "Append repeatable-read"
../lein "${LEIN_OPTIONS[@]}" -w append -i repeatable-read

log_lines "Append read-committed"
../lein "${LEIN_OPTIONS[@]}" -w append -i read-committed

log_lines "Append read-uncommitted"
../lein "${LEIN_OPTIONS[@]}" -w append -i read-uncommitted

log_lines "Non-repeatable read serializable"
../lein "${LEIN_OPTIONS[@]}" -w nonrepeatable-read -i serializable

log_lines "Non-repeatable repeatable-read"
../lein "${LEIN_OPTIONS[@]}" -w nonrepeatable-read -i repeatable-read

log_lines "mav serializable"
../lein "${LEIN_OPTIONS[@]}" -w mav -i serializable

log_lines "mav repeatable-read"
../lein "${LEIN_OPTIONS[@]}" -w mav -i repeatable-read
