#!/usr/bin/env bash
# shellcheck disable=SC2154

# Include with:
# . ./bash_lib.sh

bb_log_info() {
  set +x
  echo >&1 "INFO: $*"
  set -x
}

bb_log_warn() {
  set +x
  echo >&1 "WARNING: $*"
  set -x
}

bb_log_skip() {
  set +x
  echo >&1 "SKIP: $*"
  set -x
}

bb_log_err() {
  set +x
  echo >&2 "ERROR: $*"
  set -x
}

bb_log_ok() {
  set +x
  echo >&1 "OK: $*"
  set -x
}

err() {
  set +x
  echo >&2 "ERROR: $*"
  exit 1
}

manual_run_switch() {
  # check if we are in Buildbot CI or not
  if [[ $BB_CI != "True" ]]; then
    if [[ -z $1 ]]; then
      echo "Please provide the build URL, example:"
      echo "$0 https://buildbot.mariadb.org/#/builders/171/builds/7351"
      exit 1
    else
      # define environment variables from build properties
      for cmd in jq sudo wget; do
        command -v $cmd >/dev/null ||
          err "$cmd command not found"
      done
      if echo "$1" | grep -q "buildbot.dev.mariadb.org"; then
        BB_URL="buildbot.dev.mariadb.org"
        ARTIFACTS_URL="ci.dev.mariadb.org"
        BRANCH=dev
      else
        BB_URL="buildbot.mariadb.org"
        # shellcheck disable=SC2034
        ARTIFACTS_URL="ci.mariadb.org"
        BRANCH=main
      fi
      # get buildid
      buildid=$(wget -qO- "${1/\#/api/v2}" | jq -r '.builds[] | .buildid')
      # get build properties
      wget -q "https://$BB_URL/api/v2/builds/$buildid/properties" -O properties.json ||
        err "unable to get build properties from $1"
      # //TEMP do better with jq filtering
      for var in $(jq -r '.properties[]' properties.json | grep -v warnings-count | grep ": \[" | cut -d \" -f2); do
        export "$var"="$(jq -r ".properties[] | .${var}[0]" properties.json)"
      done
      # we need some global env vars (not provided as properties)
      wget -q "https://raw.githubusercontent.com/MariaDB/buildbot/$BRANCH/constants.py" -O constants.py ||
        err "unable to get global env vars"
      dev_branch=$(grep DEVELOPMENT_BRANCH constants.py | cut -d \" -f2)
      export development_branch="$dev_branch"
    fi
  fi
}

bb_print_env() {
  # Environment
  source /etc/os-release
  echo -e "\nDistribution: $PRETTY_NAME"
  echo "Architecture: $arch"
  echo -e "Systemd capability: $systemdCapability"
  echo "MariaDB version: ${mariadb_version/mariadb-/}"
  if [[ $test_type == "major" ]]; then
    echo "MariaDB previous major version: $prev_major_version"
  fi
  echo -e "\nDisk usage:"
  df -kT

  # make sure SELinux is in Enforcing mode
  if [[ -f /etc/selinux/config ]]; then
    selinux_status=$(getenforce)
    if [[ $selinux_status != "Enforcing" ]]; then
      bb_log_warn "Selinux is not in enforcing mode ($selinux_status)"
    else
      echo -e "\nSelinux status: $selinux_status"
    fi
  fi

  if command -v dpkg >/dev/null; then
    package_manager="dpkg -l"
  else
    package_manager="rpm -qa"
  fi
  echo -e "\nMariaDB related packages installed (should be empty):"
  $package_manager | grep -iE 'maria|mysql|galera' || true
  echo ""
}

apt_get_update() {
  bb_log_info "update apt cache"
  res=1
  for i in {1..10}; do
    if sudo apt-get update; then
      res=0
      break
    fi
    bb_log_warn "apt-get update failed, retrying ($i)"
    sleep 5
  done

  if ((res != 0)); then
    bb_log_err "apt-get update failed"
    exit $res
  fi
}

rpm_repo_dir() {
  # ID_LIKE may not exist
  set +u
  if [[ $ID_LIKE =~ ^suse* ]]; then
    echo "/etc/zypp/repos.d"
  else
    echo "/etc/yum.repos.d"
  fi
  set -u
}

rpm_pkg() {
  # ID_LIKE may not exist
  set +u
  if [[ $ID_LIKE =~ ^suse* ]]; then
    echo zypper
  else
    if command -v dnf >/dev/null; then
      echo dnf
    elif command -v yum >/dev/null; then
      echo yum
    fi
  fi
  set -u
}

rpm_pkg_makecache() {
  pkg_cmd=$(rpm_pkg)
  # Try several times, to avoid sporadic "The requested URL returned error: 404"
  made_cache=0

  set +u # ID_LIKE may not exist
  for i in {1..5}; do
    if [[ $ID_LIKE =~ ^suse* ]]; then
      sudo rm -rf "/var/cache/zypp/*"
      sudo "$pkg_cmd" clean --all
    else
      sudo rm -rf "/var/cache/$pkg_cmd/*"
      sudo "$pkg_cmd" clean all
    fi
    source /etc/os-release
    if [[ $ID == "rhel" ]]; then
      sudo subscription-manager refresh
    fi
    if [[ $ID_LIKE =~ ^suse* ]]; then
      pkg_cache="refresh"
    else
      pkg_cache="makecache"
    fi
    if sudo "$pkg_cmd" "$pkg_cache"; then
      made_cache=1
      break
    else
      bb_log_info "try several times ($i), to avoid sporadic The requested URL returned error: 404"
      sleep 5
    fi
  done
  set -u

  if ((made_cache != 1)); then
    bb_log_err "failed to make cache"
    exit 1
  fi
}

rpm_repoquery() {
  if [[ -f $(rpm_repo_dir)/MariaDB.repo ]]; then
    repo_name_tmp=$(grep -v "\#" "$(rpm_repo_dir)/MariaDB.repo" | head -n1)
    # remove brackets
    repo_name=${repo_name_tmp/\[/}
    repo_name=${repo_name/\]/}
  else
    bb_log_err "$(rpm_repo_dir)/MariaDB.repo is missing"
  fi

  # ID_LIKE may not exist
  set +u
  # return full package list from repository
  if [[ $ID_LIKE =~ ^suse* ]]; then
    zypper packages -r "${repo_name}" | grep "MariaDB" | awk -F ' \\| ' '{print $3}' #After cache is made, no need for sudo
  else
    repoquery --disablerepo=* --enablerepo="${repo_name}" -a -q |
      cut -d ":" -f1 | sort -u | sed 's/-0//'
  fi
  set -u
}

wait_for_mariadb_upgrade() {
  res=1
  for i in {1..20}; do
    if pgrep -ifa 'mysql_upgrade|mysqlcheck|mysqlrepair|mysqlanalyze|mysqloptimize|mariadb-upgrade|mariadb-check'; then
      bb_log_info "wait for mysql_upgrade to finish ($i)"
      sleep 5
    else
      res=0
      break
    fi
  done
  if ((res != 0)); then
    bb_log_err "mysql_upgrade or alike have not finished in reasonable time"
    exit $res
  fi
}

deb_setup_mariadb_mirror() {
  # stop if any further variable is undefined
  set -u
  [[ -n $1 ]] || {
    bb_log_err "missing the branch variable"
    exit 1
  }
  branch=$1
  bb_log_info "setup MariaDB repository for $branch branch"
  command -v wget >/dev/null || {
    bb_log_err "wget command not found"
    exit 1
  }
  #//TEMP it's probably better to install the last stable release here...?
  mirror_url="https://deb.mariadb.org/$branch"
  archive_url="https://archive.mariadb.org/mariadb-$branch/repo"
  if wget -q --method=HEAD "$mirror_url/$dist_name/dists/$version_name"; then
    baseurl="$mirror_url"
  elif wget -q --method=HEAD "$archive_url/$dist_name/dists/$version_name"; then
    baseurl="$archive_url"
  else
    # the correct way of handling this would be to not even start the check
    # since we know it will always fail. But apparently, it's not going to
    # happen soon in BB. Once done though, replace the warning with an error
    # and use a non-zero exit code.
    bb_log_warn "deb_setup_mariadb_mirror: $branch packages for $dist_name $version_name does not exist on deb|archive.mariadb.org"
    exit 0
  fi
  sudo sh -c "echo 'deb $baseurl/$dist_name $version_name main' >/etc/apt/sources.list.d/mariadb.list"
  sudo wget https://mariadb.org/mariadb_release_signing_key.asc -O /etc/apt/trusted.gpg.d/mariadb_release_signing_key.asc || {
    bb_log_err "mariadb repository key installation failed"
    exit 1
  }
  set +u
}

rpm_setup_mariadb_mirror() {
  # stop if any further variable is undefined
  set -u
  [[ -n $1 ]] || {
    bb_log_err "missing the branch variable"
    exit 1
  }
  branch=$1
  bb_log_info "setup MariaDB repository for $branch branch"
  command -v wget >/dev/null || {
    bb_log_err "wget command not found"
    exit 1
  }
  #//TEMP it's probably better to install the last stable release here...?
  mirror_url="https://rpm.mariadb.org/$branch/$arch"
  archive_url="https://archive.mariadb.org/mariadb-$branch/yum/$arch"
  if wget -q --method=HEAD "$mirror_url"; then
    baseurl="$mirror_url"
  elif wget -q --method=HEAD "$archive_url"; then
    baseurl="$archive_url"
  else
    # the correct way of handling this would be to not even start the check
    # since we know it will always fail. But apparently, it's not going to
    # happen soon in BB. Once done though, replace the warning with an error
    # and use a non-zero exit code.
    bb_log_warn "rpm_setup_mariadb_mirror: $branch packages for $dist_name $version_name does not exist on https://rpm.mariadb.org/"
    exit 0
  fi
  cat <<EOF | sudo tee "$(rpm_repo_dir)/MariaDB.repo"
[mariadb]
name=MariaDB
baseurl=$baseurl
# //TEMP following is not needed for all OS
# - rhel8 based OS (almalinux 8, rockylinux 8, centos 8)
module_hotfixes = 1
gpgkey=https://rpm.mariadb.org/RPM-GPG-KEY-MariaDB
gpgcheck=1
EOF

  set +u
  #ID_LIKE may not exist
  if [[ $ID_LIKE =~ ^suse* ]]; then
    sudo zypper --gpg-auto-import-keys refresh mariadb
  fi
}

deb_setup_bb_artifacts_mirror() {
  # stop if any variable is undefined
  set -u
  bb_log_info "setup buildbot artifact repository"
  sudo wget "$artifactsURL/$tarbuildnum/$parentbuildername/mariadb.sources" -O /etc/apt/sources.list.d/mariadb.sources || {
    bb_log_err "unable to download $artifactsURL/$tarbuildnum/$parentbuildername/mariadb.sources"
    exit 1
  }
  set +u
}

rpm_setup_bb_artifacts_mirror() {
  # stop if any variable is undefined
  set -u
  bb_log_info "setup buildbot artifact repository"
  sudo wget "$artifactsURL/$tarbuildnum/$parentbuildername/MariaDB.repo" -O "$(rpm_repo_dir)/MariaDB.repo" || {
    bb_log_err "unable to download $artifactsURL/$tarbuildnum/$parentbuildername/MariaDB.repo"
    exit 1
  }
  set +u
}

rpm_setup_bb_galera_artifacts_mirror() {
  # stop if any variable is undefined
  set -u
  bb_log_info "setup buildbot galera artifact repository"
  sudo wget "$artifactsURL/galera/mariadb-4.x-latest-gal-${parentbuildername/-rpm-autobake/}.repo" -O "$(rpm_repo_dir)/galera.repo" || {
    bb_log_err "unable to download $artifactsURL/galera/mariadb-4.x-latest-gal-${parentbuildername/-rpm-autobake/}.repo"
    exit 1
  }
  set +u
}

deb_setup_bb_galera_artifacts_mirror() {
  # stop if any variable is undefined
  set -u
  bb_log_info "setup buildbot galera artifact repository"
  sudo wget "$artifactsURL/galera/mariadb-4.x-latest-gal-${parentbuildername/-deb-autobake/}.sources" -O /etc/apt/sources.list.d/galera.sources || {
    bb_log_err "unable to download $artifactsURL/galera/mariadb-4.x-latest-gal-${parentbuildername/-deb-autobake/}.sources"
    exit 1
  }
  set +u
}

deb_arch() {
  case $(arch) in
    "x86_64")
      echo "amd64"
      ;;
    "x86")
      echo "i386"
      ;;
    "aarch64")
      echo "arm64"
      ;;
    "ppc64le")
      echo "ppc64el"
      ;;
    "s390x")
      echo "s390x"
      ;;
    *)
      echo "unknown arch"
      exit 1
      ;;
  esac
}

upgrade_type_mode() {
  case "$branch" in
    *galera*)
      if [[ $test_mode == "all" ]]; then
        bb_log_warn "the test in 'all' mode is not executed for galera branches"
        exit
      fi
      ;;
    "$development_branch")
      if [[ $test_mode != "server" ]]; then
        bb_log_warn "for non-stable branches the test is only run in 'test' mode"
        exit
      fi
      ;;
  esac
}

upgrade_test_type() {
  case $1 in
    "minor")
      prev_major_version=$major_version
      ;;
    "major")
      major=${major_version%.*}
      # intentionally twice, 11.5.3 has minor of 5.
      minor=${major_version##*.}
      minor=${major_version##*.}
      # with the earliest supported 11.X version
      # and make this the upgrade from 10.11
      if [ "$minor" -eq 0 ]; then
        if ((major == 11)); then
          prev_major_version="10.11"
        elif ((major == 12)); then
          prev_major_version="11.8"
        else
          bb_log_err "Unknown previous branch for $branch_tmp, please update this script"
          exit 1
        fi
      else
        prev_major_version="$major.$((minor - 1))"
      fi
      ;;
    *)
      bb_log_err "test type not provided"
      exit 1
      ;;
  esac
}

get_columnstore_logs() {
  if [[ $test_mode == "columnstore" ]]; then
    bb_log_info "storing Columnstore logs in columnstore_logs"
    set +ex
    # It is done in such a weird way, because Columnstore currently makes its logs hard to read
    # //TEMP this is fragile and weird (test that /var/log/mariadb/columnstore exist)
    for f in $(sudo ls /var/log/mariadb/columnstore | xargs); do
      f=/var/log/mariadb/columnstore/$f
      echo "----------- $f -----------" >>/home/buildbot/columnstore_logs
      sudo cat "$f" 1>>/home/buildbot/columnstore_logs 2>&1
    done
    for f in /tmp/columnstore_tmp_files/*; do
      if [ -f "$f" ]; then
        echo "----------- $f -----------" >>/home/buildbot/columnstore_logs
        sudo cat "$f" | sudo tee -a /home/buildbot/columnstore_logs 2>&1
      fi
    done
  fi
}

check_mariadb_server_and_create_structures() {
  # All the commands below should succeed
  set -e
  sudo mariadb -e "CREATE DATABASE db"
  sudo mariadb -e "CREATE TABLE db.t_innodb(a1 SERIAL, c1 CHAR(8)) ENGINE=InnoDB; INSERT INTO db.t_innodb VALUES (1,'foo'),(2,'bar')"
  sudo mariadb -e "CREATE TABLE db.t_myisam(a2 SERIAL, c2 CHAR(8)) ENGINE=MyISAM; INSERT INTO db.t_myisam VALUES (1,'foo'),(2,'bar')"
  sudo mariadb -e "CREATE TABLE db.t_aria(a3 SERIAL, c3 CHAR(8)) ENGINE=Aria; INSERT INTO db.t_aria VALUES (1,'foo'),(2,'bar')"
  sudo mariadb -e "CREATE TABLE db.t_memory(a4 SERIAL, c4 CHAR(8)) ENGINE=MEMORY; INSERT INTO db.t_memory VALUES (1,'foo'),(2,'bar')"
  sudo mariadb -e "CREATE ALGORITHM=MERGE VIEW db.v_merge AS SELECT * FROM db.t_innodb, db.t_myisam, db.t_aria"
  sudo mariadb -e "CREATE ALGORITHM=TEMPTABLE VIEW db.v_temptable AS SELECT * FROM db.t_innodb, db.t_myisam, db.t_aria"
  sudo mariadb -e "CREATE PROCEDURE db.p() SELECT * FROM db.v_merge"
  sudo mariadb -e "CREATE FUNCTION db.f() RETURNS INT DETERMINISTIC RETURN 1"
  if [[ $test_mode == "columnstore" ]]; then
    if ! sudo mariadb -e "CREATE TABLE db.t_columnstore(a INT, c VARCHAR(8)) ENGINE=ColumnStore; SHOW CREATE TABLE db.t_columnstore; INSERT INTO db.t_columnstore VALUES (1,'foo'),(2,'bar')"; then
      get_columnstore_logs
      exit 1
    fi
  fi
  set +e
}

check_mariadb_server_and_verify_structures() {
  # Print "have_xx" capabilitites for the new server
  sudo mariadb -e "select 'Stat' t, variable_name name, variable_value val from information_schema.global_status where variable_name like '%have%' union select 'Vars' t, variable_name name, variable_value val from information_schema.global_variables where variable_name like '%have%' order by t, name"
  # All the commands below should succeed
  set -e
  sudo mariadb -e "select @@version, @@version_comment"
  sudo mariadb -e "SHOW TABLES IN db"
  sudo mariadb -e "SELECT * FROM db.t_innodb; INSERT INTO db.t_innodb VALUES (3,'foo'),(4,'bar')"
  sudo mariadb -e "SELECT * FROM db.t_myisam; INSERT INTO db.t_myisam VALUES (3,'foo'),(4,'bar')"
  sudo mariadb -e "SELECT * FROM db.t_aria; INSERT INTO db.t_aria VALUES (3,'foo'),(4,'bar')"
  bb_log_info "If the next INSERT fails with a duplicate key error,"
  bb_log_info "it is likely because the server was not upgraded or restarted after upgrade"
  sudo mariadb -e "SELECT * FROM db.t_memory; INSERT INTO db.t_memory VALUES (1,'foo'),(2,'bar')"
  sudo mariadb -e "SELECT COUNT(*) FROM db.v_merge"
  sudo mariadb -e "SELECT COUNT(*) FROM db.v_temptable"
  sudo mariadb -e "CALL db.p()"
  sudo mariadb -e "SELECT db.f()"

  if [[ $test_mode == "columnstore" ]]; then
    if ! sudo mariadb -e "SELECT * FROM db.t_columnstore; INSERT INTO db.t_columnstore VALUES (3,'foo'),(4,'bar')"; then
      get_columnstore_logs
      exit 1
    fi
  fi
  set +e
}

control_mariadb_server() {
  bb_log_info "$1 MariaDB server"
  case "$systemdCapability" in
    yes)
      sudo systemctl "$1" mariadb
      ;;
    no)
      sudo /etc/init.d/mysql "$1"
      ;;
  esac
}

store_mariadb_server_info() {
  # We need sudo here because the mariadb local root configured this way, not because we want special write permissions for the resulting file.
  # pre-commit check has an issue with it, so instead of adding an exception before each line, we add a piped sort, which should be bogus,
  sudo mariadb --skip-column-names -e "select @@version" | awk -F'-' '{ print $1 }' >"/tmp/version.$1"
  sudo mariadb --skip-column-names -e "select engine, support, transactions, savepoints from information_schema.engines order by engine" | sort >"./engines.$1"
  sudo mariadb --skip-column-names -e "select plugin_name, plugin_status, plugin_type, plugin_library, plugin_license \
                                       from information_schema.all_plugins order by plugin_name" | sort >"./plugins.$1"
  sudo mariadb --skip-column-names -e "select 'Stat' t, variable_name name, variable_value val
                                       from information_schema.global_status where variable_name like '%have%' \
                                       union \
                                       select 'Vars' t, variable_name name, variable_value val \
                                       from information_schema.global_variables where variable_name like '%have%' \
                                       order by t, name" | sort >"./capabilities.$1"
}

check_upgraded_versions() {
  for file in /tmp/version.old /tmp/version.new; do
    [[ -f $file ]] || {
      bb_log_err "$file not found"
      exit 1
    }
  done
  # check that a major upgrade was done
  if [[ $test_type == "major" ]]; then
    old_branch_digit=$(cut -d "." -f1 </tmp/version.old)
    old_major_digit=$(cut -d "." -f2 </tmp/version.old)
    new_branch_digit=$(cut -d "." -f1 </tmp/version.new)
    new_major_digit=$(cut -d "." -f2 </tmp/version.new)
    # treat 10.11.* -> 11.0.* upgrade specifically
    if ((old_branch_digit == 10)) && ((old_major_digit == 11)); then
      if ((new_branch_digit == 11)) && ((new_major_digit != 0)); then
        bb_log_err "This does not look like a major upgrade from 10.11 to 11.0:"
        diff -u /tmp/version.old /tmp/version.new
        exit 1
      fi
    elif ((old_branch_digit == 11)) && ((old_major_digit == 8)); then
      if ((new_branch_digit == 12)) && ((new_major_digit != 0)); then
        bb_log_err "This does not look like a major upgrade from 11.8 to 12.0:"
        diff -u /tmp/version.old /tmp/version.new
        exit 1
      fi
    else
      old_major_digit_incr=$((old_major_digit + 1))
      ((old_major_digit_incr == new_major_digit)) || {
        bb_log_err "This does not look like a major upgrade:"
        diff -u /tmp/version.old /tmp/version.new
        exit 1
      }
    fi
  fi
  if diff -u /tmp/version.old /tmp/version.new; then
    bb_log_err "Server version has not changed after upgrade."
    bb_log_err "It can be a false positive if we forgot to bump version after release"
    bb_log_err "or if it is a development tree that is based on an old version"
    exit 1
  fi

  res=0
  errors=""
  engines_disappeared_or_changed=$(comm -23 ./engines.old ./engines.new | wc -l)
  set +x
  if ((engines_disappeared_or_changed != 0)); then
    bb_log_err "Found changes in the list of engines:"
    diff -u ./engines.old ./engines.new
    errors="$errors engines,"
    res=1
  fi
  if [[ $test_type == "minor" ]]; then

    # We are using temporary files for further comparison, because we will need to make
    # some adjustments to them to avoid false positives, but we want original files
    # to be stored by buildbot
    for f in ldd-main ldd-columnstore reqs-main reqs-columnstore plugins capabilities; do
      if [ -e "./${f}.old" ]; then
        cp "./${f}.old" "./${f}.old.cmp"
        cp "./${f}.new" "./${f}.new.cmp"
      fi
    done

    # Permanent adjustments
    sed -i '/libstdc++.so.6(GLIBCXX/d;/libstdc++.so.6(CXXABI/d' ./reqs-*.cmp
    # Don't compare subversions of libsystemd.so (e.g. libsystemd.so.0(LIBSYSTEMD_227)(64bit))
    sed -i '/libsystemd.so.[0-9]*(LIBSYSTEMD_/d' ./reqs-*.cmp
    # Ignore shells, the number of which always changes
    sed -i '/^\/bin\/sh$/d' ./reqs-*.cmp

    # Here is the place for temporary adjustments,
    # when legitimate changes in dependencies happen between minor versions.
    # The adjustments should be done to .cmp files, and removed after the release
    #

    # Remove after Q3 2025 release (MDEV-36234)
    sed -i '/libaio.so/d;/liburing.so/d;/libaio1/d' ./reqs-*.cmp
    sed -i '/libaio.so/d;/liburing.so/d' ./ldd-*.cmp
    sed -i '/lsof/d' ./reqs-*.cmp

    #Account for mariadb-plugin-mroonga diffs in Debian
    sed -i '/liblz4-1/d' ./reqs-*.cmp
    sed -i '/liblz4.so.1/d' ./ldd-*.cmp
    sed -i '/libmecab2/d' ./reqs-*.cmp
    sed -i '/libmecab.so.2/d' ./ldd-*.cmp

    # End of temporary adjustments

    set -o pipefail
    bb_log_info "Comparing old and new ldd output for installed binaries"
    # We are not currently comparing it for Columnstore, too much trouble for nothing
    if ! diff -U1000 ./ldd-main.old.cmp ./ldd-main.new.cmp | (grep -E '^[-+]|^ =' || true); then
      bb_log_err "Found changes in ldd output, see above"
      errors="$errors ldd,"
      res=1
    else
      bb_log_info "ldd OK"
    fi

    bb_log_info "Comparing old and new package requirements"
    # We are not currently comparing it for Columnstore, but we may need to in the future
    if ! diff -U150 ./reqs-main.old.cmp ./reqs-main.new.cmp | (grep -E '^ [^ ]|^[-+]' || true); then
      bb_log_err "Found changes in package requirements, see above"
      errors="$errors requirements,"
      res=1
    else
      bb_log_info "Package requirements OK"
    fi

    bb_log_info "Comparing old and new server capabilities ('%have%' variables)"
    if ! diff -u ./capabilities.old.cmp ./capabilities.new.cmp; then
      bb_log_err "Found changes in server capabilities, see above"
      errors="$errors capabilities,"
      res=1
    else
      bb_log_info "Capabilities OK"
    fi

    echo "Comparing old and new plugins"
    # Columnstore version changes often, we'll ignore it
    grep -i columnstore ./plugins.old.cmp >/tmp/columnstore.old
    grep -i columnstore ./plugins.new.cmp >/tmp/columnstore.new
    if ! diff -u /tmp/columnstore.old /tmp/columnstore.new; then
      bb_log_warn "Columnstore version changed. Downgraded to a warning as it is usually intentional"
      sed -i '/COLUMNSTORE/d;/Columnstore/d' ./plugins.*.cmp
    fi

    if ! diff -u ./plugins.old.cmp ./plugins.new.cmp; then
      bb_log_err "Found changes in available plugins, see above"
      errors="$errors plugins,"
      res=1
    else
      bb_log_info "Plugins OK"
    fi
  fi
  if [ -n "$errors" ]; then
    bb_log_err "Problems were found with:$errors see above output for details"
  fi
  exit $res
}

# Collect package requirements and ldd for all binaries included into packages.
# Expects "old" and "new" as the first argument,
# "deb" or "rpm" as the second argument,
# and $package_list to be set by the time of execution
collect_dependencies() {
  [[ $test_type == "minor" ]] || return
  old_or_new=$1
  pkgtype=$2
  bb_log_info "Collecting dependencies for the ${old_or_new} server"
  set +x
  # Spider_package_list variable does not exist for RPM upgrades.
  set +u
  for p in ${package_list} ${spider_package_list}; do
    # TEMP: Skip debuginfo packages as ldd is not reliable. See MDBF-887
    if [[ "$p" =~ -debuginfo$ ]]; then
      continue
    fi

    if [[ "$p" =~ columnstore ]]; then
      suffix="columnstore"
    else
      suffix="main"
    fi
    set -u

    echo "-----------------" >>"./reqs-${suffix}.${old_or_new}"
    echo "$p:" >>"./reqs-${suffix}.${old_or_new}"
    if [ "$pkgtype" == "rpm" ]; then
      rpm -q -R "$p" | awk '{print $1}' | sort | grep -vE '/usr/bin/env|/usr/bin/bash' >>"./reqs-${suffix}.${old_or_new}"
    else
      # We need sudo here for the apt-cache command, not for redirection
      # shellcheck disable=SC2024
      sudo apt-cache depends "$p" --no-suggests --no-conflicts --no-breaks --no-replaces --no-enhances | sort >>"./reqs-${suffix}.${old_or_new}"
    fi

    # Collect LDD output for files installed by the package on the system
    if [[ ${p,,} != "mariadb-test"* ]]; then
      if [ "$pkgtype" == "rpm" ]; then
        filelist=$(rpm -ql "$p" | sort)
      else
        filelist=$(dpkg-query -L "$p" | sort)
      fi
      echo "====== Package $p" >>"./ldd-${suffix}.${old_or_new}"
      for f in $filelist; do
        # We do want to match literally here, not as regex
        # shellcheck disable=SC2076
        if [[ "$f" =~ "/.build-id/" ]]; then
          continue
        fi
        sudo ldd "$f" >/dev/null 2>&1 || continue
        echo "=== $f" >>"./ldd-${suffix}.${old_or_new}"
        sudo ldd "$f" | sort | sed 's/(.*)//' >>"./ldd-${suffix}.${old_or_new}"
      done
    fi
  done
  set -x
}
