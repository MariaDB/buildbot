#!/usr/bin/env bash

bindistname="%(prop:bindistname)s"

cd /usr/local/"$bindistname"/mysql-test || cd /usr/local/"$bindistname"/mariadb-test || err /usr/local/"$bindistname"/mariadb-test
if ! sudo su -s /bin/sh -c "perl mysql-test-run.pl --mem rocksdb.1st 2>&1" mysql | grep -E 'RocksDB is not compiled|Could not find'; then
    sudo su -s /bin/sh -c "perl mysql-test-run.pl --suite=rocksdb* --skip-test=rocksdb_hotbackup* --verbose-restart --force --parallel=4 --retry=3 --mem --max-save-core=0 --max-save-datadir=1" mysql
fi
