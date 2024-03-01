#!/usr/bin/env bash
# shellcheck disable=SC2154

set -e

# Buildbot installation test script
# this script can be called manually by providing the build URL as argument:
# ./rpm-install.sh "https://buildbot.mariadb.org/#/builders/368/builds/695"

# load common functions
# shellcheck disable=SC1091
. ./bash_lib.sh

# yum/dnf switch
pkg_cmd=$(rpm_pkg)

# function to be able to run the script manually (see bash_lib.sh)
manual_run_switch "$1"

# Mandatory variables
for var in arch master_branch; do
  if [[ -z $var ]]; then
    bb_log_err "$var is not defined"
    exit 1
  fi
done

bb_print_env

set -x

rpm_pkg_makecache

sudo "$pkg_cmd" search mysql | { grep "^mysql" || true; }
sudo "$pkg_cmd" search maria | { grep "^maria" || true; }
sudo "$pkg_cmd" search percona | { grep percona || true; }

# setup repository for galera dependency
rpm_setup_bb_galera_artifacts_mirror

# setup artifact repository
rpm_setup_bb_artifacts_mirror

rpm_pkg_makecache

# install all packages
pkg_list=$(rpm_repoquery) ||
  bb_log_err "Unable to retrieve package list from repository"

echo "$pkg_list" | xargs sudo "$pkg_cmd" -y install

sh -c 'g=/usr/lib*/galera*/libgalera_smm.so; echo -e "[galera]\nwsrep_provider=$g"' | sudo tee /etc/my.cnf.d/galera.cnf
case "$systemdCapability" in
  yes)
    if ! sudo systemctl start mariadb; then
      sudo journalctl -lxn 500 --no-pager -u mariadb.service
      sudo systemctl -l status mariadb.service --no-pager
      exit 1
    fi
    ;;
  no)
    sudo /etc/init.d/mysql restart
    ;;
  *)
    bb_log_warn "should never happen, check your configuration (systemdCapability property is not set or is set to a wrong value)"
    ;;
esac

sudo mariadb -e 'drop database if exists test; create database test; use test; create table t(a int primary key) engine=innodb; insert into t values (1); select * from t; drop table t;'
if find rpms/*.rpm | grep -qi columnstore; then
  sudo mariadb --verbose -e "create database cs; use cs; create table cs.t_columnstore (a int, b char(8)); insert into cs.t_columnstore select seq, concat('val',seq) from seq_1_to_10; select * from cs.t_columnstore"
  sudo systemctl restart mariadb
  sudo mariadb --verbose -e "select * from cs.t_columnstore; update cs.t_columnstore set b = 'updated'"
  sudo systemctl restart mariadb-columnstore
  sudo mariadb --verbose -e "update cs.t_columnstore set a = a + 10; select * from cs.t_columnstore"
fi
sudo mariadb -e 'show global status like "wsrep%%"'
bb_log_info "test for MDEV-18563, MDEV-18526"
set +e
control_mariadb_server stop

sleep 1
sudo pkill -9 mysqld
command -v mariadb-install-db >/dev/null || {
  bb_log_err "mariadb-install-db command not found"
  exit 1
}
sudo mariadb-install-db --no-defaults --user=mysql --plugin-maturity=unknown

bb_log_ok "all done"
