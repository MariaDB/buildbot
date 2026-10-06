# master-docker-nonstandard and master-docker-nonstandard-2

Server builders with configurations the autogen masters can't make, on Docker latent workers, split across two masters.

| Master | Builders |
| --- | --- |
| master-docker-nonstandard | Other compilers (`-aocc`, `-icc`), Valgrind, RocksDB, full test suites (`amd64-ubuntu-2204-fulltest`), bintars (`amd64-centos-7-bintar`, `amd64-almalinux-8-bintar`), debug builds on aarch64, ppc64le and s390x, tests of client libraries (`-eco-pymysql`, `-eco-mysqljs`) |
| master-docker-nonstandard-2 | 32-bit full test suites (`x86-debian-12-fulltest`, `-fulltest-debug`), Jepsen (`amd64-ubuntu-2204-jepsen-mariadb`) |

Most are started like any server builder, from `SUPPORTED_PLATFORMS` in [constants.py](../constants.py) (see [Server builders](../docs/server-builders.md)). The `-eco-` builders no longer run: `amd64-debian-10`, which started them after its tests, is gone. Jepsen is started by `tarball-docker` for `jpsn-*` branches.

Add new special builders to [master-migration](../master-migration/README.md) instead, which is where these are meant to move.
