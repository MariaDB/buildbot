#!/usr/bin/env bash

# When the libvirt master starts, it creates an ssh connection to the worker
# machine for each defined worker. If for any reason that ssh connection drops
# (for example on a restart of the libvirtd daemon), then there will be build
# failures because workers are no more available. The master doesn't handle at
# all this and a master restart is needed.
# See: https://jira.mariadb.org/browse/MDBF-415

# This needs to be called as ExecStartPost= in the systemd unit file.
# See: /etc/systemd/system/buildbot-master-libvirt.service

err() {
  echo >&2 "ERROR: $*"
  exit 1
}

watchdog() {
  GET_SSH_CNX_SCRIPT="get_ssh_cnx_num.py"
  [[ -f $GET_SSH_CNX_SCRIPT ]] ||
    err "$GET_SSH_CNX_SCRIPT not found"

  # $GET_SSH_CNX_SCRIPT needs some pip libraries, thus we need to use
  # buildmaster venv
  VAR_PYTHON_VENV="/home/buildmaster/buildbot/.venv"
  [[ -d $VAR_PYTHON_VENV ]] ||
    err "$VAR_PYTHON_VENV does not exist"

  while true; do
    FAIL=0
    VAR_QEMU_SSH_CONF=$($VAR_PYTHON_VENV/bin/python $GET_SSH_CNX_SCRIPT)
    # shellcheck disable=SC2009
    VAR_QEMU_SSH_CONNEXION=$(ps -ef | grep buildbot | grep -c "qemu:///")

    if ((VAR_QEMU_SSH_CONF != VAR_QEMU_SSH_CONNEXION)); then
      FAIL=1
    fi

    if ((FAIL == 0)); then
      /bin/systemd-notify WATCHDOG=1
      sleep $((WATCHDOG_USEC / 2000000))
    else
      sleep 1
    fi
  done
}

watchdog &
