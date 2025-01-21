#!/bin/bash

set -e

yumdownloader --source gnutls-devel
yum-builddep -y gnutls-*.src.rpm
rpm -ivh gnutls-*.src.rpm
sed -i 's/--disable-static/--enable-static \\\n--disable-tests/g' ~/rpmbuild/SPECS/gnutls.spec
sed -i 's/export LDFLAGS="-Wl,--no-add-needed"/export LDFLAGS="-Wl,--copy-dt-needed-entries -fpic -fPIC"/g' ~/rpmbuild/SPECS/gnutls.spec
sed -i 's/make %{?_smp_mflags}/make %{?_smp_mflags} CFLAGS="-fpic -fPIC" CXX_FLAGS="-fpic -fPIC"/g' ~/rpmbuild/SPECS/gnutls.spec
rpmbuild -bc ~/rpmbuild/SPECS/gnutls.spec
mv -v ~/rpmbuild/BUILD/gnutls-*/lib/.libs/libgnutls.a local/lib
rm -rf ~/rpmbuild gnutls-*.src.rpm
