#!/usr/bin/env bash

set -ex

err() {
  echo >&2 "ERROR: $*"
  exit 1
}

bindistname="%(prop:bindistname)s"

df -kT
cd buildbot
sudo rm -Rf /usr/local/"$bindistname"
sudo tar zxf "$bindistname".tar.gz -C /usr/local/
cd /usr/local/"$bindistname"
sudo /usr/sbin/useradd mysql
sudo sudo chown -R mysql .
sudo chgrp -R mysql .
sudo bin/mysql --version
sudo scripts/mysql_install_db --no-defaults --user=mysql
sudo chown -R root .
sudo chown -R mysql data

sudo chown -R mysql mysql-test ||
  sudo chown -R mysql mariadb-test

echo "Test for MDEV-18563, MDEV-18526"

set +e
for p in /bin /sbin /usr/bin /usr/sbin /usr/local/bin /usr/local/sbin /usr/local/"$bindistname"/scripts; do
  if [[ -x "$p"/mysql_install_db ]]; then
    sudo "$p"/mysql_install_db --no-defaults --user=mysql --plugin-maturity=unknown
  else
    echo "$p/mysql_install_db does not exist"
  fi
done
sudo scripts/mysql_install_db --no-defaults --user=mysql --plugin-maturity=unknown

if ldd lib/plugin/ha_connect.so | grep libodbc.so.1 | grep 'not found'; then
  if [ -e /usr/lib64/libodbc.so.2 ]; then
    sudo ln -s /usr/lib64/libodbc.so.2 /usr/lib64/libodbc.so.1
  elif [ -e /usr/lib/libodbc.so.2 ]; then
    sudo ln -s /usr/lib/libodbc.so.2 /usr/lib/libodbc.so.1
  fi
fi

cd mysql-test || cd mariadb-test
if test -f suite/plugins/pam/pam_mariadb_mtr.so; then
  for p in /lib*/security /lib*/*/security; do
    test -f "$p"/pam_unix.so && sudo cp -v suite/plugins/pam/pam_mariadb_mtr.so "$p"/
  done
  sudo cp -v suite/plugins/pam/mariadb_mtr /etc/pam.d/
fi
perl mysql-test-run.pl --verbose-restart --force --parallel=4 \
    --retry=3 --vardir="$(readlink -f /dev/shm/var)" \
    --max-save-core=0 --max-save-datadir=1
