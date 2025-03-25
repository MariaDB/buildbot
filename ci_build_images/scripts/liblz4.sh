#!/bin/bash

set -e

yumdownloader --source lz4-devel
yum-builddep -y lz4-*.src.rpm
rpm -ivh lz4-*.src.rpm
sed -i 's/%make_build/%make_build CFLAGS="-fpic -fPIC" CXX_FLAGS="-fpic -fPIC"/g' ~/rpmbuild/SPECS/lz4.spec
rpmbuild -bc ~/rpmbuild/SPECS/lz4.spec
mv -v ~/rpmbuild/BUILD/lz4-*/lib/liblz4.a local/lib
rm -rf ~/rpmbuild lz4-*.src.rpm
