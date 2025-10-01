#!/usr/bin/env bash

set -e

# load common functions
# shellcheck disable=SC1091
. ./bash_lib.sh

trap 'collect_logs' EXIT

bb_print_env

control_mariadb_server restart

set +e

res=0

#----------------
# Basic pam_unix
#----------------

set -e

sudo tee /etc/pam.d/mariadb <<EOF
auth required pam_unix.so audit
account required pam_unix.so audit
EOF

# PAM v2

sudo mariadb -e "INSTALL SONAME 'auth_pam'; CREATE USER 'buildbot'@'localhost' IDENTIFIED VIA pam USING 'mariadb'"
if ! mysql -ubuildbot -ptest -e "SHOW GRANTS" ; then
  res=1
  bb_log_err "Authentication with PAM v2 (pam_unix) failed"
fi
sudo mariadb -e "UNINSTALL SONAME 'auth_pam'"
if mysql -ubuildbot -ptest -e "SHOW GRANTS" > /dev/null 2>&1 ; then
  res=1
  bb_log_err "User authenticated via PAM v2 (pam_unix) could still connect after uninstalling plugin"
fi

if ((res == 0)); then
  bb_log_info "PAM v2 Authentication test successful"
fi

# PAM v1

sudo mariadb -e "INSTALL SONAME 'auth_pam_v1'"

set +e
sudo groupadd shadow
sudo usermod -a -G shadow mysql
sudo chown root:shadow /etc/shadow
sudo chmod g+r /etc/shadow
set -e

control_mariadb_server restart

if ! mysql -ubuildbot -ptest -e "SHOW GRANTS" ; then
  res=1
  bb_log_err "Authentication with PAM v1 (pam_unix) failed"
fi
sudo mariadb -e "UNINSTALL SONAME 'auth_pam_v1'"
if mysql -ubuildbot -ptest -e "SHOW GRANTS" > /dev/null 2>&1 ; then
  res=1
  bb_log_err "User authenticated via PAM v1 (pam_unix) could still connect after uninstalling plugin"
fi

if ((res == 0)); then
  bb_log_info "PAM v1 Authentication test successful"
fi

#----------------
# MTR
#----------------

# PATH can differ between MariaDB versions and distros
for db in mysql mariadb; do
  for dir in \
    /usr/share/$db-test \
    /usr/share/$db/$db-test; do
    [[ -d "$dir" ]] && cd "$dir" && break 2
  done
done

if [[ -f suite/plugins/pam/pam_mariadb_mtr.so ]]; then
  for p in /lib*/security /lib*/*/security ; do
    [[ -f "$p/pam_unix.so" ]] && sudo cp -v suite/plugins/pam/pam_mariadb_mtr.so "$p"/
  done
  sudo cp -v suite/plugins/pam/mariadb_mtr /etc/pam.d/
fi

if ! sudo su mysql -s /bin/sh -c "perl mysql-test-run.pl --verbose-restart --force --vardir=/dev/shm/var_pam --suite=plugins --do-test=pam" ; then
  res=1
  bb_log_err "MTR PAM tests failed"
fi

set +e
if ((res != 0)); then
  exit $res
fi
