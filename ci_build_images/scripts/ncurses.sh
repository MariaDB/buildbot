#!/bin/bash

set -e

yumdownloader --source ncurses-devel
yum-builddep -y ncurses-*.src.rpm
rpmbuild --recompile ncurses-*.src.rpm
mv -v ~/rpmbuild/BUILDROOT/ncurses-*/usr/lib64/*.a local/lib
rm -rf ~/rpmbuild ncurses-*.src.rpm
