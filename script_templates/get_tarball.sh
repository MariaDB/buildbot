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

for cmd in awk wget sha256sum; do
  command -v $cmd >/dev/null ||
    err "$cmd command not found"
done

[[ -d $d ]] || mkdir $d
tarball="${mariadb_version}.tar.gz"
f="${tarbuildnum}/$tarball"

verify_checksum() {
  echo "verify checksum"
  wget -qO- "$artifacts_url/$tarbuildnum/sha256sums.txt" | tee sha256sums.txt | sha256sum -c -

  if [ $? ]; then
    echo "checksum match"
    rm sha256sums.txt
    return 0
  else
    echo "checksum does not match"
    sha256sum "$tarball"
    echo "previous calculation"
    cat sha256sums.txt
    rm sha256sums.txt
    return 1
  fi
}

download_tarball() {
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
    err "download tarball failed"
  fi
}

pushd "$d"
if [[ -f $tarball ]]; then
  echo "$tarball already present"
  if verify_checksum; then
    true
  else
    echo "download tarball again"
    rm -f $tarball
    download_tarball
    if verify_checksum; then
      true
    else
      err "checksum does not match, aborting"
    fi
  fi
else
  echo "$tarball does not exist, download tarball"
  download_tarball
  if verify_checksum "$tarball"; then
    true
  else
    err "checksum does not match, aborting"
  fi
fi
popd

echo "extract $d/$tarball"
#//TEMP path on AIX are specific
os=$(uname -s)
if [[ $os == "AIX" ]]; then
  tar -xzf $d/$tarball
else
  tar -xzf $d/$tarball --strip-components=1
fi
echo "done"
