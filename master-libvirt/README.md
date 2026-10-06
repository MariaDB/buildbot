# master-libvirt

Tests installing and upgrading the server packages built by the `-autobake` builders, in libvirt VMs. An `-autobake` build triggers them once it has saved its packages, so they run only on the branches whose packages are saved.

## Builders

Generated from [os_info.yaml](../os_info.yaml) (see [Server builders](../docs/server-builders.md#platforms-os_infoyaml)), for each `<arch>-<os>-<type>-autobake`:

| Builder | Tests |
| --- | --- |
| `...-install` | Installing the packages, then PAM authentication |
| `...-minor-upgrade-all`, `...-minor-upgrade-columnstore` | Upgrading from the last release of the same series |
| `...-major-upgrade` | Upgrading from the previous series |
| `...-distro-upgrade` | Upgrading from the distribution's own MariaDB package |

The packages for RHEL are also tested on AlmaLinux and Rocky Linux, the `install_only` entries of `os_info.yaml`.

## Scripts

The builders download their scripts (`deb-install.sh`, `rpm-upgrade.sh`, ... and `bash_lib.sh`) from [scripts/](../scripts/) on GitHub, from the branch of the environment: `main` for production, `dev` for dev. A change to these scripts is live on production as soon as it is merged to `main`, without a deployment, so test it on dev first.

## VMs

Each builder has one VM, a `LibVirtWorker` named `bb-<libvirt host>-<os>-<version>-<arch>`, which runs one build at a time. The libvirt host of each architecture, and how to connect to it, are set in `libvirt_workers` in `master-private.cfg`. Buildbot finds the VM among the host's libvirt domains by that name, boots it before a build and shuts it down after.

Every build starts on a clean VM. On the libvirt hosts, a qemu hook (`/etc/libvirt/hooks/qemu`, from the `bb_worker_vm` role of the sysadmin repository) creates `<VM name>-tmp.qcow2`, a copy-on-write layer over the base image `<VM name>.qcow2` in `/var/lib/libvirt/images/`, before the VM starts, and deletes it after the VM stops. The VM runs on that layer, so nothing a build writes is kept.

The VMs must exist before the builders that use them are deployed. They are defined in the sysadmin repository on [git.mariadb.org](https://git.mariadb.org), and have to be synchronized and deployed to the hosts. Dev and production use different libvirt hosts, so a new platform is usually:

1. deployed to the dev hosts;
1. merged to `dev`, and tested on dev;
1. deployed to the production hosts;
1. merged to `main`, and deployed.

The master connects to each libvirt host over ssh, with `master-libvirt/id_ed25519` and `known_hosts`, which are not in git. It opens one connection per VM and doesn't reopen it if it drops, for example when libvirtd restarts: the master then has to be restarted ([MDBF-415](https://jira.mariadb.org/browse/MDBF-415)). [get_ssh_cnx_num.py](get_ssh_cnx_num.py) prints the number of connections expected, which [watchdog_libvirt.sh](watchdog_libvirt.sh) compares with the open ones.
