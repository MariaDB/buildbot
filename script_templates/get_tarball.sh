#!/usr/bin/env bash

set -o errexit
set -o pipefail
set -o posix

err() {
  echo >&2 "ERROR: $*"
  exit 1
}

typeset -r d="./packages"
typeset -r tarbuildnum="%(prop:tarbuildnum)s"
typeset -r mariadb_version="%(prop:mariadb_version)s"

artifacts_url=${ARTIFACTS_URL:-https://ci.mariadb.org}

command -v wget >/dev/null ||
  err "wget command not found"

[[ -d $d ]] || mkdir $d
tarball="${mariadb_version}.tar.gz"
f="${tarbuildnum}/$tarball"

# Do not use flock for AIX/MacOS/FreeBSD
os=$(uname -s)
use_flock=""
if [[ $os != "AIX" && $os != "Darwin" && $os != "FreeBSD" ]]; then
  use_flock="flock $d/$tarball"
fi
cmd="$use_flock wget --progress=bar:force:noscroll -cO $d/$tarball $artifacts_url/$f"

res=1
for i in {1..10}; do
  if eval "$cmd"; then
    res=0
    break
  else
    sleep "$i"
  fi
done
if ((res != 0)); then
  exit $res
fi

tar -xzf $d/$tarball --strip-components=1
