#!/bin/bash

set -e

yumdownloader --source libaio-devel
yum-builddep -y libaio-*.src.rpm
rpmbuild --recompile libaio-*.src.rpm
mv -v ~/rpmbuild/BUILD/libaio-*/src/*.a local/lib
rm -rf ~/rpmbuild libaio-*.src.rpm
