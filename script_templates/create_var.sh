#!/usr/bin/env bash

set -o errexit
set -o pipefail
set -o posix

err() {
  echo >&2 "ERROR: $*"
  exit 1
}

if [[ -z $MTR_LOG_DIR ]]; then
  log_dir="./buildbot"
else
  log_dir="$MTR_LOG_DIR"
fi

if [[ -d ./mysql-test/var ]]; then
  typeset extra=""
  for dir in \
    ./mysql-test/var/log/*/core* \
    ./mysql-test/var/*/log/*/mysqld.*/data/core* \
    ./mysql-test/var/*/log/*/core*; do
    if compgen -G "$dir" >/dev/null; then
      extra="$extra $dir"
    fi
  done
  if [[ -f sql/mysqld ]] && [[ ! -L sql/mysqld ]]; then
    extra="$extra sql/mysqld"
  fi
  [[ -f sql/mariadbd ]] && extra="$extra sql/mariadbd"
fi

tar czvf var.tar.gz mysql-test/var/*/log/*.err mysql-test/var/log "$extra"
mv var.tar.gz "./${log_dir}/logs/${MTR_TEST_NAME}"
