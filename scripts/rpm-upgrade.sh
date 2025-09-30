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

package_version=${mariadb_version/mariadb-/}

bb_print_env

# This test can be performed in four modes:
# - 'server' -- only mariadb-server is installed (with whatever dependencies it pulls) and upgraded.
# - 'all'    -- all provided packages are installed and upgraded, except for Columnstore
# - 'deps'   -- only a limited set of main packages is installed and upgraded,
#               to make sure upgrade does not require new dependencies
# - 'columnstore' -- mariadb-server and mariadb-plugin-columnstore are installed
bb_log_info "Current test mode: $test_mode"

set -x

rpm_pkg_makecache

rpm_setup_mariadb_mirror "$prev_major_version"

# Define the list of packages to install/upgrade
case $test_mode in
  all)
    # retrieve full package list from repo
    package_list=$(rpm_repoquery) ||
      bb_log_err "unable to retrieve package list from repository"
    package_list=$(echo "$package_list" | grep -viE 'galera|columnstore')
    alternative_names_package_list=$package_list
    bb_log_warn "Due to MCOL-4120 and other issues, Columnstore upgrade will be tested separately"
    ;;
  server)
    package_list="MariaDB-server MariaDB-client"
    alternative_names_package_list=$package_list
    if [[ "$test_type" == "distro" ]]; then
      if [[ "$ID_LIKE" =~ ^suse.* ]]; then
        alternative_names_package_list="mariadb mariadb-client"
      else
        alternative_names_package_list="mariadb-server mariadb"
      fi
    fi
    ;;
  columnstore)
    package_list=$(rpm_repoquery)
    if ! echo "$package_list" | grep -q columnstore-engine; then
      bb_log_warn "Columnstore was not found in the released packages, the test will not be run"
      exit
    fi
    package_list="MariaDB-server MariaDB-columnstore-engine"
    alternative_names_package_list=$package_list
    ;;
  *)
    bb_log_err "unknown test mode ($test_mode)"
    exit 1
    ;;
esac

bb_log_info "Package_list: $package_list"

# ID_LIKE may not exist
set +u
if [[ $ID_LIKE =~ ^suse* ]]; then
  sudo "$pkg_cmd" clean --all
  pkg_cmd_options="-n"
  pkg_cmd_upgrade="update"
else
  sudo "$pkg_cmd" clean all
  pkg_cmd_options="-y"
  pkg_cmd_upgrade="upgrade"
fi
set -u

# Install previous release
echo "$alternative_names_package_list" | xargs sudo "$pkg_cmd" "$pkg_cmd_options" install ||
  bb_log_err "installation of a previous release failed, see the output above"
#fi

# Start the server, check that it is working and create some structures
case $(expr "$prev_major_version" '<' "10.1")"$systemdCapability" in
  0yes)
    sudo systemctl start mariadb
    if [ "$pkg_cmd" != "zypper" ]; then
      sudo systemctl enable mariadb
    else
      bb_log_warn "due to MDEV-23044 mariadb service won't be enabled in the test"
    fi
    sudo systemctl status mariadb --no-pager
    ;;
  *)
    sudo /etc/init.d/mysql start
    ;;
esac

# shellcheck disable=SC2181
if (($? != 0)); then
  bb_log_err "Server startup failed"
  sudo cat /var/log/messages | grep -iE 'mysqld|mariadb'
  sudo cat /var/lib/mysql/*.err
  exit 1
fi

check_mariadb_server_and_create_structures

# Store information about the server before upgrade
collect_dependencies old rpm
store_mariadb_server_info old

# If the tested branch has the same version as the public repository,
# upgrade won't work properly. For releasable branches, we will return an error
# urging to bump the version number. For other branches, we will abort the test
# with a warning (which nobody will read). This is done upon request from
# development, as temporary branches might not be rebased in a timely manner
[[ -f /tmp/version.old ]] && old_version=$(cat /tmp/version.old)
if [[ $package_version == "$old_version" ]]; then
  bb_log_err "server version $package_version has already been released. Bump the version number!"
  for b in $releasable_branches; do
    if [[ $b == "$branch" ]]; then
      exit 1
    fi
  done
  bb_log_warn "the test will be skipped, as upgrade will not work properly"
  exit
fi

rpm_setup_bb_galera_artifacts_mirror
rpm_setup_bb_artifacts_mirror
if [[ "$test_type" =~ ^(major|distro)$ ]]; then
  # major upgrade (remove then install)
  echo "$package_list" | xargs sudo "$pkg_cmd" "$pkg_cmd_options" install
else
  # minor upgrade (upgrade works)
  echo "$package_list" | xargs sudo "$pkg_cmd" "$pkg_cmd_options" "$pkg_cmd_upgrade"
fi
# set +e

# Check that no old packages have left after upgrade
# The check is only performed for all-package-upgrade, because
# for selective ones some implicitly installed packages might not be upgraded
if [[ $test_mode == "all" ]]; then
  if [[ $is_main_tree == "yes" ]]; then
    rpm -qa | grep -iE 'mysql|maria' | grep "$(cat /tmp/version.old)"
  else
    rpm -qa | grep -iE 'mysql|maria' | grep "$(cat /tmp/version.old)" | grep -v debuginfo
  fi
  # shellcheck disable=SC2181
  if (($? == 0)); then
    bb_log_err "old packages have been found after upgrade"
    exit 1
  fi
fi

# Optionally (re)start the server
set -e
if [[ "$test_type" =~ ^(major|distro)$ ]] || [[ $test_mode == "columnstore" ]]; then
  control_mariadb_server restart
fi

# Make sure that the new server is running
if sudo mariadb -e "select @@version" | grep "$old_version"; then
  bb_log_err "the server was not upgraded or was not restarted after upgrade"
  exit 1
fi

# Run mariadb-upgrade for non-GA branches (minor upgrades in GA branches
# shouldn't need it)
if [[ $major_version == "$development_branch" ]] || [[ "$test_type" =~ ^(major|distro)$ ]]; then
  sudo mariadb-upgrade
fi

# Check that the server is functioning and previously created structures are available
check_mariadb_server_and_verify_structures

# Store information about the server after upgrade
collect_dependencies new rpm
store_mariadb_server_info new

check_upgraded_versions

bb_log_ok "all done"
