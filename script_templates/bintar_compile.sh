#!/usr/bin/env bash

# This is a template file for a shell script that is used to compile a binary tarball.
# The script CANNOT BE EXECUTED DIRECTLY, it is a template for the buildbot to use.

set -o errexit
set -o nounset
set -o pipefail
set -o posix

err() {
  echo >&2 "ERROR: $*"
  exit 1
}

#distdirname="%(prop:distdirname)s"
branch="%(prop:branch)s"
cmake="%(prop:additional_args)s"
extra=""

# TODO handle galera part
#case $distdirname in
#  *-10.[23].*)
#    # centos5 sort doesn't support -V
#    latest=$(wget --no-check-certificate https://hasky.askmonty.org/galera/ -O -|grep -o galera-25'\.[0-9]\.[0-9][0-9]' |sort|tail -1)
#  ;;
#  *)
#    latest=$(wget --no-check-certificate https://hasky.askmonty.org/galera/ -O -|grep -o galera-26'\.[0-9]\+\.[0-9]\+' |sort -V|tail -1)
#  ;;
#esac
#if [ -n "$latest" ] ; then
#  wget --no-check-certificate https://hasky.askmonty.org/galera/$latest/bintar/$latest""" + suffix + "-" + arch + """.tar.gz
#  if [ -r galera-*.tar.gz ] ; then
#      tar xf galera-*.tar.gz
#      p=$(echo $HOME/galera-*/usr)
#      extra="-DEXTRA_FILES=$p/lib/libgalera_smm.so=lib;$p/lib/galera/libgalera_smm.so=lib/galera"
#      for f in $p/bin/*; do
#        extra="$extra;$f=bin"
#      done
#  fi
#fi
cd buildbot/build || err "cd buildbot/build"
mkdir mkbin
cd mkbin
echo "$PATH"
echo "$SHELL"

if [[ -d "$HOME"/local/lib ]]; then
  export CMAKE_LIBRARY_PATH="$HOME/local/lib"
fi
if [[ -d "$HOME"/local/share/pkgconfig ]]; then
  export PKG_CONFIG_PATH="$HOME/local/share/pkgconfig"
fi
case $branch in
  preview-*)
    EV=$branch
    EV=-DEXTRA_VERSION=-${EV#preview-*.*-}
    ;;
esac
export JAVA_HOME=/usr/lib/jvm/java
cmake -DBUILD_CONFIG=mysql_release -DWITH_READLINE=1 "$EV $extra $cmake" ..
make -j"$(nproc)" package VERBOSE=1
basename mariadb-*.tar.gz .tar.gz >../../bindistname.txt
mv "$(cat ../../bindistname.txt).tar.gz" ../
