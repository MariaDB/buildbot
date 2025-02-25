#!/bin/bash

set -e

yumdownloader --source xz-devel
yum-builddep -y xz-*.src.rpm
rpm -ivh xz-*.src.rpm
sed -i 's/--disable-static/--disable-shared --enable-static --with-pic/g' ~/rpmbuild/SPECS/xz.spec
sed -i 's/CFLAGS="/CFLAGS="-fpic -fPIC /g' ~/rpmbuild/SPECS/xz.spec
sed -i 's/export CFLAGS/export CFLAGS\nCXXFLAGS="-fpic -fPIC"\nexport CXXFLAGS/g' ~/rpmbuild/SPECS/xz.spec
sed -i '/\*\.a/d' ~/rpmbuild/SPECS/xz.spec
rpmbuild -bc ~/rpmbuild/SPECS/xz.spec
mv -v ~/rpmbuild/BUILD/xz-*/src/liblzma/.libs/liblzma.a local/lib
rm -rf ~/rpmbuild xz-*.src.rpm
