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

if [[ $distro == "sles123" ]]; then
  distro="sles12"
fi

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
  *)
    bb_log_err "unknown test mode ($test_mode)"
    exit 1
    ;;
esac

# case $test_mode in
#   all | deps | columnstore)
#     if [[ $test_mode == "all" ]]; then
#       if echo "$package_list" | grep -qi columnstore; then
#         bb_log_warn "due to MCOL-4120 and other issues, Columnstore upgrade will be tested separately"
#       fi
#       package_list=$(echo "$package_list" | grep MariaDB |
#         grep -viE 'galera|columnstore' | sed -e 's/<name>//' |
#         sed -e 's/<\/name>//' | sort -u | xargs)
#     elif [[ $test_mode == "deps" ]]; then
#       package_list=$(echo "$package_list" |
#         grep -iE 'MariaDB-server|MariaDB-test|MariaDB-client|MariaDB-common|MariaDB-compat' |
#         sed -e 's/<name>//' | sed -e 's/<\/name>//' | sort -u | xargs)
#     elif [[ $test_mode == "columnstore" ]]; then
#       if ! echo "$package_list" | grep -q columnstore; then
#         bb_log_warn "columnstore was not found in the released packages, the test will not be run"
#         exit
#       fi
#       package_list="MariaDB-server MariaDB-columnstore-engine"
#     fi

#     if [[ $arch == ppc* ]]; then
#       package_list=$(echo "$package_list" | xargs -n1 | sed -e 's/MariaDB-compat//gi' | xargs)
#     fi
#     ;;
#   server)
#     package_list="MariaDB-server MariaDB-client"
#     ;;
#   *)
#     bb_log_err "unknown test mode: $test_mode"
#     exit 1
#     ;;
# esac

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

# # Store dependency information for old binaries/libraries:
# # - names starting with "mysql*" in the directory where mysqld is located;
# # - names starting with "mysql*" in the directory where mysql is located;
# # - everything in the plugin directories installed by any MariaDB packages
# set +x
# for i in $(sudo which mysqld | sed -e 's/mysqld$/mysql\*/') $(which mysql | sed -e 's/mysql$/mysql\*/') $(rpm -ql $(rpm -qa | grep MariaDB | xargs) | grep -v 'mysql-test' | grep -v '/debug/' | grep '/plugin/' | sed -e 's/[^\/]*$/\*/' | sort | uniq | xargs); do
#   echo "=== $i"
#   ldd $i | sort | sed 's/(.*)//'
# done >/home/buildbot/ldd.old
# set -x

# # Prepare yum/zypper configuration for installation of the new packages
# # //TEMP again not sure this is needed
# set -e
# if [[ $test_type == "major" ]]; then
#   bb_log_info "remove old packages for major upgrade"
#   packages_to_remove=$(rpm -qa | grep 'MariaDB-' | awk -F'-' '{print $1"-"$2}' | xargs)
#   sudo sh -c "$remove_command $packages_to_remove"
#   rpm -qa | grep -iE 'maria|mysql' || true
# fi
# if [[ $test_mode == "deps" ]]; then
#   sudo mv "$repo_location/MariaDB.repo" /tmp
#   sudo rm -rf "$repo_location/*"
#   sudo mv /tmp/MariaDB.repo "$repo_location/"
#   sudo sh -c "$cleanup_command"
# fi

# Install the new packages:
# Between 10.3 and 10.4(.2), required galera version changed from galera(-3) to galera-4.
# It means that there will be no galera-4 in the "old" repo, and it's not among the local RPMs.
# So, we need to add a repo for it
# //TEMP this needs to be fixed
# if [[ $test_type == "major" ]] && ((${major_version/10./} >= 3)) && ((${prev_major_version/10./} <= 4)); then
#   sudo sh -c "echo '[galera]
# name=Galera
# baseurl=https://yum.mariadb.org/galera/repo4/rpm/$arch
# gpgkey=https://yum.mariadb.org/RPM-GPG-KEY-MariaDB
# gpgcheck=1' > $repo_location/galera.repo"
# fi

# //TEMP upgrade does not work without this but why? Can't we fix it?
if [[ $test_type == "major" ]]; then
  bb_log_info "remove old packages for major upgrade"
  packages_to_remove=$(rpm -qa | grep 'MariaDB-' | awk -F'-' '{print $1"-"$2}')
  echo "$packages_to_remove" | xargs sudo "$pkg_cmd" "$pkg_cmd_options" remove
  rpm -qa | grep -iE 'maria|mysql' || true
fi

rpm_setup_bb_galera_artifacts_mirror
rpm_setup_bb_artifacts_mirror
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
if [[ $test_type == "major" ]]; then
  control_mariadb_server restart
fi

# Make sure that the new server is running
if sudo mariadb -e "select @@version" | grep "$old_version"; then
  bb_log_err "the server was not upgraded or was not restarted after upgrade"
  exit 1
fi

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

# # Dependency information for new binaries/libraries
# set +x
# for i in $(sudo which mysqld | sed -e 's/mysqld$/mysql\*/') $(which mysql | sed -e 's/mysql$/mysql\*/') $(rpm -ql $(rpm -qa | grep MariaDB | xargs) | grep -v 'mysql-test' | grep -v '/debug/' | grep '/plugin/' | sed -e 's/[^\/]*$/\*/' | sort | uniq | xargs); do
#   echo "=== $i"
#   ldd "$i" | sort | sed 's/(.*)//'
# done >/home/buildbot/ldd.new
# set -x
# case "$systemdCapability" in
#   yes)
#     ls -l /usr/lib/systemd/system/mariadb.service
#     ls -l /etc/systemd/system/mariadb.service.d/migrated-from-my.cnf-settings.conf
#     ls -l /etc/init.d/mysql || true
#     systemctl status mariadb.service --no-pager
#     systemctl status mariadb --no-pager
#     # Not done for SUSE due to MDEV-23044
#     if [[ "$distro" != *"sles"* ]] && [[ "$distro" != *"suse"* ]]; then
#       # Major upgrade for RPMs is remove / install, so previous configuration
#       # could well be lost
#       if [[ "$test_type" == "major" ]]; then
#         sudo systemctl enable mariadb
#       fi
#       systemctl is-enabled mariadb
#       systemctl status mysql --no-pager
#       systemctl status mysqld --no-pager
#     fi
#     ;;
#   no)
#     bb_log_info "Steps related to systemd will be skipped"
#     ;;
#   *)
#     bb_log_err "It should never happen, check your configuration (systemdCapability property is not set or is set to a wrong value)"
#     exit 1
#     ;;
# esac
# set +e

# # Until $development_branch is GA, the list of plugins/engines might be unstable, skipping the check
# # For major upgrade, no point to do the check at all
# if [[ $major_version != "$development_branch" ]] && [[ $test_type != "major" ]]; then
#   # This output is for informational purposes
#   diff -u /tmp/engines.old /tmp/engines.new
#   diff -u /tmp/plugins.old /tmp/plugins.new
#   # Only fail if there are any disappeared/changed engines or plugins
#   disappeared_or_changed=$(comm -23 /tmp/engines.old /tmp/engines.new | wc -l)
#   if ((disappeared_or_changed != 0)); then
#     bb_log_err "the lists of engines in the old and new installations differ"
#     exit 1
#   fi
#   disappeared_or_changed=$(comm -23 /tmp/plugins.old /tmp/plugins.new | wc -l)
#   if ((disappeared_or_changed != 0)); then
#     bb_log_err "the lists of available plugins in the old and new installations differ"
#     exit 1
#   fi
#   if [[ $test_mode == "all" ]]; then
#     set -o pipefail
#     if wget -q --timeout=20 --no-check-certificate "https://raw.githubusercontent.com/MariaDB/mariadb.org-tools/master/buildbot/baselines/ldd.${major_version}.${distro}.${arch}" -O /tmp/ldd.baseline; then
#       ldd_baseline=/tmp/ldd.baseline
#     else
#       ldd_baseline=/home/buildbot/ldd.old
#     fi
#     if ! diff -U1000 $ldd_baseline /home/buildbot/ldd.new | (grep -E '^[-+]|^ =' || true); then
#       bb_log_err "something has changed in the dependencies of binaries or libraries. See the diff above"
#       exit 1
#     fi
#   fi
#   set +o pipefail
# fi

check_upgraded_versions

bb_log_ok "all done"
