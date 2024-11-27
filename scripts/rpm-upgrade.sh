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
distro=$version_name

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
    bb_log_warn "Due to MCOL-4120 and other issues, Columnstore upgrade will be tested separately"
    ;;
  server)
    package_list="MariaDB-server MariaDB-client"
    ;;
  columnstore)
    package_list=$(rpm_repoquery)
    if ! echo "$package_list" | grep -q columnstore-engine; then
      bb_log_warn "Columnstore was not found in the released packages, the test will not be run"
      exit
    fi
    package_list="MariaDB-server MariaDB-columnstore-engine"
    ;;
  *)
    bb_log_err "unknown test mode ($test_mode)"
    exit 1
    ;;
esac

bb_log_info "Package_list: $package_list"

# # //TEMP this needs to be implemented once we have SLES VM in new BB
# # Prepare yum/zypper configuration for installation of the last release
# if which zypper; then
#   repo_location=/etc/zypp/repos.d
#   install_command="zypper --no-gpg-checks install --from mariadb -y"
#   cleanup_command="zypper clean --all"
#   remove_command="zypper remove -y"
#   # Since there is no reasonable "upgrade" command in zypper which would
#   # pick up RPM files needed to upgrade existing packages, we have to use "install".
#   # However, if we run "install *.rpm", it will install all packages, regardless
#   # the test mode, and we will get a lot of differences in contents after upgrade
#   # (more plugins, etc.). So, instead for each package that we are going to install,
#   # we'll also find an RPM file which provides it, and will use its name in
#   # in the "upgrade" (second install) command
#   if [[ $test_mode == "all" ]]; then
#     rm -f rpms/*columnstore*.rpm
#     rpms_for_upgrade="rpms/*.rpm"
#   else
#     rpms_for_upgrade=""
#     for p in $package_list; do
#       for f in rpms/*.rpm; do
#         if rpm -qp "$f" --provides | grep -i "^$p ="; then
#           rpms_for_upgrade="$rpms_for_upgrade $f"
#           break
#         fi
#       done
#     done
#   fi
#   upgrade_command="zypper --no-gpg-checks install -y $rpms_for_upgrade"

# As of now (February 2018), RPM packages do not support major upgrade.
# To imitate it, we will remove previous packages and install new ones.
# //TEMP is this still true??
#else
#
# repo_location=/etc/yum.repos.d
# install_command="sudo $pkg_cmd -y --nogpgcheck install"
# cleanup_command="sudo $pkg_cmd clean all"
# upgrade_command="sudo $pkg_cmd -y --nogpgcheck upgrade"
# if [[ $test_type == "major" ]]; then
#   upgrade_command="sudo $pkg_cmd -y --nogpgcheck install"
# fi
# # //TEMP not sure about the reason of this
# # if $pkg_cmd autoremove 2>&1 | grep -q 'need to be root'; then
# #   remove_command="sudo $pkg_cmd -y autoremove"
# # else
# #   remove_command="sudo $pkg_cmd -y remove"
# # fi
# remove_command="sudo $pkg_cmd -y autoremove"

# Workaround for TODO-1479 (errors upon reading from SUSE repos):
# sudo rm -rf
# /etc/zypp/repos.d/SUSE_Linux_Enterprise_Server_12_SP3_x86_64:SLES12-SP3-Updates.repo
# /etc/zypp/repos.d/SUSE_Linux_Enterprise_Server_12_SP3_x86_64:SLES12-SP3-Pool.repo

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
echo "$package_list" | xargs sudo "$pkg_cmd" "$pkg_cmd_options" install ||
  bb_log_err "installation of a previous release failed, see the output above"
#fi

# Start the server, check that it is working and create some structures
case $(expr "$prev_major_version" '<' "10.1")"$systemdCapability" in
  0yes)
    sudo systemctl start mariadb
    if [[ $distro != *"sles"* ]] && [[ $distro != *"suse"* ]]; then
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

# //TEMP upgrade does not work without this but why? Can't we fix it?
if [[ $test_type == "major" ]]; then
  bb_log_info "remove old packages for major upgrade"
  packages_to_remove=$(rpm -qa | grep 'MariaDB-' | awk -F'-' '{print $1"-"$2}')
  echo "$packages_to_remove" | xargs sudo "$pkg_cmd" "$pkg_cmd_options" remove
  rpm -qa | grep -iE 'maria|mysql' || true
fi

rpm_setup_bb_galera_artifacts_mirror
rpm_setup_bb_artifacts_mirror

# Any of the below steps could fail
# This is where the new packages are processed from
trap save_failure_logs ERR
set -e

if [[ $test_type == "major" ]]; then
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
if [[ $test_type == "major" ]] || [[ $test_mode == "columnstore" ]]; then
  control_mariadb_server restart
fi

bb_log_info "Make sure that the new server is running"
sudo mariadb -e "select @@version" | grep "$old_version"

# Run mariadb-upgrade for non-GA branches (minor upgrades in GA branches
# shouldn't need it)
if [[ $major_version == "$development_branch" ]] || [[ $test_type == "major" ]]; then
  sudo mariadb-upgrade
fi

# Check that the server is functioning and previously created structures are available
check_mariadb_server_and_verify_structures

# Store information about the server after upgrade
collect_dependencies new rpm
store_mariadb_server_info new

check_upgraded_versions

bb_log_ok "all done"
