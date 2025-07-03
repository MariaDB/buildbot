#!/usr/bin/env bash
# shellcheck disable=SC2154

set -e

# Buildbot installation test script
# this script can be called manually by providing the build URL as argument:
# ./deb-install.sh "https://buildbot.mariadb.org/#/builders/171/builds/7351"

# load common functions
# shellcheck disable=SC1091
. ./bash_lib.sh

# load OS variables
# shellcheck disable=SC1091
. /etc/os-release

# function to be able to run the script manually (see bash_lib.sh)
manual_run_switch "$1"

bb_print_env

# check that no related packages are present
# this should be a fresh and clean VM
if dpkg -l | grep -iE 'maria|mysql|galera'; then
  bb_log_err "This VM should not contain the previous packages"
  exit 1
fi

# check for needed commands
for cmd in wget gunzip; do
  command -v $cmd >/dev/null || { bb_log_err "$cmd command not found" && exit 1; }
done

# setup repository //TEMP this should not be needed since installation is
# supposed to be done directly from artifacts, but maybe it is for dependencies?
# deb_setup_mariadb_mirror "$master_branch"

# setup galera repository (we need to test mariadb with latest produced galera version)A
deb_setup_bb_galera_artifacts_mirror

# setup repository for BB artifacts
deb_setup_bb_artifacts_mirror

# Once repo are created with aptly, adapt below:
# wget -O - "${artifactsURL}/${tarbuildnum}/${parentbuildername}/dists/${VERSION_CODENAME}/main/binary-$(deb_arch)/Packages.gz" | gunzip >Packages
wget "${artifactsURL}/${tarbuildnum}/${parentbuildername}/debs/Packages"

set -x

# Due to MDEV-14622 and its effect on Spider installation,
# Spider has to be installed separately after the server
package_list=$(grep "^Package:" Packages |
  grep -vE 'galera|spider|columnstore' |
  awk '{print $2}' | xargs)
if grep -qi spider Packages; then
  spider_package_list=$(grep "^Package:" Packages |
    grep 'spider' | awk '{print $2}' | xargs)
fi
arch=$(deb_arch)
if grep -qi columnstore Packages; then
  if [[ $arch != "amd64" ]] && [[ $arch != "arm64" ]]; then
    bb_log_warn "Due to MCOL-4123, Columnstore won't be installed on $arch"
  else
    columnstore_package_list=$(grep "^Package:" Packages |
      grep 'columnstore' | awk '{print $2}' | xargs)
  fi
fi

# apt get update may be running in the background (Ubuntu start).
apt_get_update

sudo sh -c "DEBIAN_FRONTEND=noninteractive MYSQLD_STARTUP_TIMEOUT=180 \
  apt-get install -y $package_list $columnstore_package_list"

# MDEV-14622: Wait for mysql_upgrade running in the background to finish
wait_for_mariadb_upgrade

# To avoid confusing errors in further logic, do an explicit check whether the
# service is up and running
if [[ $systemdCapability == "yes" ]]; then
  if ! sudo systemctl status mariadb --no-pager; then
    sudo journalctl -xe --no-pager
    bb_log_warn "mariadb service isn't running properly after installation"
    if echo "$package_list" | grep -q columnstore; then
      bb_log_info "It is likely to be caused by ColumnStore"
      bb_log_info "problems upon installation, getting the logs"
      set +e
      # It is done in such a weird way, because Columnstore currently makes its
      # logs hard to read
      for f in $(sudo ls /var/log/mariadb/columnstore | xargs); do
        f=/var/log/mariadb/columnstore/$f
        echo "----------- $f -----------"
        sudo cat "$f"
      done
      for f in /tmp/columnstore_tmp_files/*; do
        echo "----------- $f -----------"
        sudo cat "$f"
      done
    fi
    bb_log_err "mariadb service didn't start properly after installation"
    exit 1
  fi
fi

# Due to MDEV-14622 and its effect on Spider installation,
# Spider has to be installed separately after the server
if [[ -n $spider_package_list ]]; then
  sudo sh -c "DEBIAN_FRONTEND=noninteractive MYSQLD_STARTUP_TIMEOUT=180 \
    apt-get install -y $spider_package_list"
fi

sudo mariadb --verbose -e "create database test; \
  use test; \
  create table t(a int primary key) engine=innodb; \
  insert into t values (1); \
  select * from t; \
  drop table t; \
  drop database test; \
  create user galera identified by 'gal3ra123'; \
  grant all on *.* to galera;"
sudo mariadb -e "select @@version"
bb_log_info "test for MDEV-18563, MDEV-18526"
set +e

control_mariadb_server stop

sleep 1
sudo pkill -9 mysqld
for p in /bin /sbin /usr/bin /usr/sbin /usr/local/bin /usr/local/sbin; do
  if test -x $p/mariadb-install-db; then
    sudo $p/mariadb-install-db --no-defaults --user=mysql --plugin-maturity=unknown
  else
    bb_log_info "$p/mariadb-install-db does not exist"
  fi
done
sudo mariadb-install-db --no-defaults --user=mysql --plugin-maturity=unknown
set +e
## Install mariadb-test for further use
# sudo sh -c "DEBIAN_FRONTEND=noninteractive MYSQLD_STARTUP_TIMEOUT=180 apt-get install -y mariadb-test"
if dpkg -l | grep -i spider >/dev/null; then
  bb_log_warn "Workaround for MDEV-22979, otherwise server hangs further in SST steps"
  sudo sh -c "DEBIAN_FRONTEND=noninteractive MYSQLD_STARTUP_TIMEOUT=180 \
    apt-get remove --allow-unauthenticated -y mariadb-plugin-spider" || true
  sudo sh -c "DEBIAN_FRONTEND=noninteractive MYSQLD_STARTUP_TIMEOUT=180 \
    apt-get purge --allow-unauthenticated -y mariadb-plugin-spider" || true
fi
if dpkg -l | grep -i columnstore >/dev/null; then
  bb_log_warn "Workaround for a bunch of Columnstore bugs"
  bb_log_warn "otherwise mysqldump in SST steps fails when Columnstore returns errors"
  sudo sh -c "DEBIAN_FRONTEND=noninteractive MYSQLD_STARTUP_TIMEOUT=180 \
    apt-get remove --allow-unauthenticated -y mariadb-plugin-columnstore" || true
  sudo sh -c "DEBIAN_FRONTEND=noninteractive MYSQLD_STARTUP_TIMEOUT=180 \
    apt-get purge --allow-unauthenticated -y mariadb-plugin-columnstore" || true
fi

bb_log_ok "all done"
