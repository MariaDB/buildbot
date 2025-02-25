#!/bin/bash

set -e

yumdownloader --source libzstd
yum-builddep -y zstd-*.src.rpm
rpm -ivh zstd-*.src.rpm
rpmbuild -bp ~/rpmbuild/SPECS/zstd.spec
make CFLAGS=-fPIC -C ~/rpmbuild/BUILD/zstd-*
mv -v ~/rpmbuild/BUILD/zstd-*/lib/libzstd.a local/lib
rm -rf ~/rpmbuild zstd-*.src.rpm
