#!/usr/bin/env bash
# shellcheck disable=SC2154

set -e

# Buildbot minor upgrade test script
# this script can be called manually by providing the build URL as argument:
# ./script.sh "https://buildbot.mariadb.org/#/builders/171/builds/7351"

# load common functions
# shellcheck disable=SC1091
. ./bash_lib.sh

# function to be able to run the script manually (see bash_lib.sh)
manual_run_switch "$1"

upgrade_type_mode
upgrade_test_type "$test_type"

bb_print_env

# This test can be performed in four modes:
# - 'server' -- only mariadb-server is installed (with whatever dependencies it pulls) and upgraded.
# - 'all'    -- all provided packages are installed and upgraded, except for Columnstore
# - 'deps'   -- only a limited set of main packages is installed and upgraded,
#               to make sure upgrade does not require new dependencies
# - 'columnstore' -- mariadb-server and mariadb-plugin-columnstore are installed
bb_log_info "Current test mode: $test_mode"

set -x

# Prepare apt repository configuration for installation of the previous major
# version
deb_setup_mariadb_mirror "$prev_major_version"

get_packages_file_mirror() {
  set -u
  if ! wget "$baseurl/$dist_name/dists/$version_name/main/binary-$(deb_arch)/Packages"
  then
    bb_log_err "Could not find the 'Packages' file for $dist_name $version_name on deb|archive.mariadb.org."
    exit 1
  fi
  set +u
}

# Define the list of packages to install/upgrade
case $test_mode in
  all)
    get_packages_file_mirror
    if grep -qi columnstore Packages; then
      bb_log_warn "due to MCOL-4120 (Columnstore leaves the server shut down)"
      bb_log_warn "and other bugs Columnstore upgrade is tested separately"
    fi
    package_list=$(grep "^Package:" Packages |
      grep -vE 'galera|spider|columnstore' |
      awk '{print $2}' | sort -u | xargs)
    if grep -qi spider Packages; then
      bb_log_warn "due to MDEV-14622 Spider will be installed separately after the server"
      spider_package_list=$(grep "^Package:" Packages |
        grep 'spider' | awk '{print $2}' |
        sort -u | xargs)
    fi
    if grep -si tokudb Packages; then
      # For the sake of installing TokuDB, disable hugepages
      sudo sh -c "echo never > /sys/kernel/mm/transparent_hugepage/enabled" || true
    fi
    ;;
  deps)
    package_list="mariadb-server mariadb-client mariadb-common mariadb-test mysql-common libmysqlclient18"
    ;;
  server)
    package_list=mariadb-server
    ;;
  columnstore)
    get_packages_file_mirror
    if ! grep columnstore Packages >/dev/null; then
      bb_log_warn "Columnstore was not found in packages, the test will not be run"
      exit
    elif [[ $version_name == "sid" ]]; then
      bb_log_warn "Columnstore isn't necessarily built on Sid, the test will be skipped"
      exit
    fi
    package_list="mariadb-server mariadb-plugin-columnstore"
    ;;
  *)
    bb_log_err "unknown test mode: $test_mode"
    exit 1
    ;;
esac
bb_log_info "Package_list: $package_list"

# We need to pin directory to ensure that installation happens from MariaDB
# repo rather than from the default distro repo
if [[ $prev_major_version == "10.2" ]]; then
  mirror="archive.mariadb.org"
else
  mirror="deb.mariadb.org"
fi
sudo sh -c "echo 'Package: *' > /etc/apt/preferences.d/release"
sudo sh -c "echo 'Pin: origin $mirror' >> /etc/apt/preferences.d/release"
sudo sh -c "echo 'Pin-Priority: 1000' >> /etc/apt/preferences.d/release"

# apt get update may be running in the background (Ubuntu start).
apt_get_update

# Install previous release
# Debian installation/upgrade/startup always attempts to execute mysql_upgrade, and
# also run mysqlcheck and such. Due to MDEV-14622, they are subject to race condition,
# and can be executed later or even omitted.
# We will wait till they finish, to avoid any clashes with SQL we are going to execute
wait_for_mariadb_upgrade

if ! sudo sh -c "DEBIAN_FRONTEND=noninteractive MYSQLD_STARTUP_TIMEOUT=180 \
  apt-get -o Dpkg::Options::=--force-confnew install --allow-unauthenticated -y $package_list"; then
  bb_log_err "Installation of a previous release failed, see the output above"
  exit 1
fi

wait_for_mariadb_upgrade

if [[ -n $spider_package_list ]]; then
  if ! sudo sh -c "DEBIAN_FRONTEND=noninteractive MYSQLD_STARTUP_TIMEOUT=180 \
    apt-get -o Dpkg::Options::=--force-confnew install --allow-unauthenticated -y $spider_package_list"; then
    bb_log_err "Installation of Spider from the previous release failed, see the output above"
    exit 1
  fi
  wait_for_mariadb_upgrade
fi

# To avoid confusing errors in further logic, do an explicit check
# whether the service is up and running
if [[ $systemdCapability == "yes" ]]; then
  if ! sudo systemctl status mariadb --no-pager; then
    sudo journalctl -xe --no-pager
    get_columnstore_logs
    bb_log_err "mariadb service didn't start properly after installation"
    exit 1
  fi
fi

if [[ $test_mode == "all" ]]; then
  bb_log_warn "Due to MDEV-23061, an extra server restart is needed"
  control_mariadb_server restart
fi

# Check that the server is functioning and create some structures
check_mariadb_server_and_create_structures

# Store information about the server before upgrade
collect_dependencies old deb
store_mariadb_server_info old

if [[ $test_mode == "deps" ]]; then
  # For the dependency check, only keep the local repo //TEMP what does this do???
  sudo sh -c "grep -iE 'deb .*file|deb-src .*file' /etc/apt/sources.list.backup >/etc/apt/sources.list"
  sudo rm -f /etc/apt/sources.list.d/*
else
  sudo cp /etc/apt/sources.list.backup /etc/apt/sources.list
  sudo rm /etc/apt/sources.list.d/mariadb.list
fi
sudo rm /etc/apt/preferences.d/release

deb_setup_bb_galera_artifacts_mirror
deb_setup_bb_artifacts_mirror
apt_get_update

# Install the new packages
if ! sudo sh -c "DEBIAN_FRONTEND=noninteractive MYSQLD_STARTUP_TIMEOUT=180 \
  apt-get -o Dpkg::Options::=--force-confnew install --allow-unauthenticated -y $package_list"; then
  bb_log_err "installation of the new packages failed, see the output above"
  exit 1
fi
wait_for_mariadb_upgrade

if [[ -n $spider_package_list ]]; then
  if ! sudo sh -c "DEBIAN_FRONTEND=noninteractive MYSQLD_STARTUP_TIMEOUT=180 \
    apt-get -o Dpkg::Options::=--force-confnew install --allow-unauthenticated -y $spider_package_list"; then
    bb_log_err "Installation of the new Spider packages failed, see the output above"
    exit 1
  fi
  wait_for_mariadb_upgrade
fi
if [[ $test_mode == "columnstore" ]]; then
  bb_log_warn "Due to MCOL-4120 an extra server restart is needed"
  control_mariadb_server restart
fi

# Wait till mysql_upgrade, mysqlcheck and such are finished:
# Again, wait till mysql_upgrade is finished, to avoid clashes; and for
# non-stable versions, it might be necessary, so run it again just in case it
# was omitted
wait_for_mariadb_upgrade

# run mysql_upgrade for non GA branches
if [[ $major_version == "$development_branch" ]]; then
  sudo mariadb-upgrade
fi

# Make sure that the new server is running
if sudo mariadb -e "select @@version" | grep "$(cat /tmp/version.old)"; then
  bb_log_err "the server was not upgraded or was not restarted after upgrade"
  exit 1
fi

# Check that no old packages have left after upgrade:
# The check is only performed for all-package-upgrade, because for selective
# ones some implicitly installed packages might not be upgraded
if [[ $test_mode == "all" ]]; then
  if dpkg -l | grep -iE 'mysql|maria' | grep "$(cat /tmp/version.old)"; then
    bb_log_err "old packages have been found after upgrade"
    exit 1
  fi
fi

# Check that the server is functioning and previously created structures are
# available
check_mariadb_server_and_verify_structures

# Store information about the server after upgrade
collect_dependencies new deb
store_mariadb_server_info new

check_upgraded_versions

bb_log_ok "all done"
