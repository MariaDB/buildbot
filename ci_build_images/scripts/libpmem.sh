#!/bin/bash

set -e

yumdownloader --source libpmem-devel
yum-builddep -y pmdk-*.src.rpm
rpmbuild --recompile pmdk-*.src.rpm
mv -v ~/rpmbuild/BUILD/pmdk-*/src/nondebug/libpmem.a local/lib
rm -rf ~/rpmbuild pmdk-*.src.rpm