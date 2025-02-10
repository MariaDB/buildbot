#!/bin/bash
# shellcheck disable=SC2086
# shellcheck disable=SC2098
# shellcheck disable=SC2097
# shellcheck disable=SC2046

set -e

### TODO Healthy approach. Doesn't work.

#------------------------------------------------------------------------------
# This is basically following the SPEC file steps through Install
# One cannot disable --with-shared because the SPEC file assumes shared is enabled
# and it will fail if not.
# Although we rsync the static libraries / headers from BUILDROOT
# and ${CURSES_INCLUDE_PATH} is OK i.e. CURSES_INCLUDE_PATH:/scripts/local/include
# I still cannot find several functions in libncurses.a

#-- Found Curses: /scripts/local/lib/libcurses.a
#-- Looking for tputs in /scripts/local/lib/libcurses.a
#-- Looking for tputs in /scripts/local/lib/libcurses.a - not found
#-- Looking for tputs in tinfo
#-- Looking for tputs in tinfo - found
#-- Looking for setupterm in tinfo
#-- Looking for setupterm in tinfo - found
#-- Looking for vidattr in tinfo
#-- Looking for vidattr in tinfo - not found
#-- Looking for include files curses.h, term.h
#-- Looking for include files curses.h, term.h - found

# So I suppose there's something in the spec file that I'm not aware of
# This is what I've tried

#yumdownloader --source ncurses-devel
#yum-builddep -y ncurses-*.src.rpm
#rpm -ivh ncurses-*.src.rpm
## Make functions available in libncurses.a
#sed -i '/--with-terminfo-dirs/d' $HOME/rpmbuild/SPECS/ncurses.spec
#sed -i '/--with-termlib=tinfo/d' $HOME/rpmbuild/SPECS/ncurses.spec
#sed -i '/--disable-wattr-macros/d' $HOME/rpmbuild/SPECS/ncurses.spec
## Build the package
#rpmbuild -bi $HOME/rpmbuild/SPECS/ncurses.spec
## Remove unwanted files
#rm -rf $HOME/rpmbuild/BUILDROOT/ncurses-*/usr/lib
#rm -rf $HOME/rpmbuild/BUILDROOT/ncurses-*/usr/src
#rm -rf $HOME/rpmbuild/BUILDROOT/ncurses-*/usr/usr
## lib64 dir is the one we want but without .so files
#mv $HOME/rpmbuild/BUILDROOT/ncurses-*/usr/lib64 $HOME/rpmbuild/BUILDROOT/ncurses-*/usr/lib
#rsync -av --exclude='*.so.*' $HOME/rpmbuild/BUILDROOT/ncurses-*/usr/* /scripts/local
## Further cleanup
#rm -rf $HOME/rpmbuild
#rm -f /scripts/ncurses-*.src.rpm

#------------------------------------------------------------------------------


# Second approach. Current.
# In this approach we only prepare the source dir with applied patches
# by using rpmbuild -bp

# Then we manually configure it, with /scripts/local/ as the target,
# This way we bypass the rest of the steps in the SPEC file
# This is why we need to manually symlink the include/ncurses headers to ../
# The above operation was managed by packaging, so that CMAKE
# can find the headers in ${CURSES_INCLUDE_PATH} i.e. /scripts/local/include

yumdownloader --source ncurses-devel
yum-builddep -y ncurses-*.src.rpm
rpm -ivh ncurses-*.src.rpm
rpmbuild -bp $HOME/rpmbuild/SPECS/ncurses.spec
cd $HOME/rpmbuild/BUILD/ncurses-*/

CFLAGS="-fpic -fPIC" CXXFLAGS=${CFLAGS} ./configure --without-manpages --without-tests --without-progs --with-terminfo-dirs="/etc/terminfo:/lib/terminfo:/usr/share/terminfo" --with-xterm-kbs=del --disable-termcap --prefix=/scripts/local/
make -j"$(nproc)" install
mv /scripts/local/include/ncurses/* /scripts/local/include/
# Snippet from spec file %INSTALL
for l in /scripts/local/include/*.h; do
    ln -s ../$(basename $l) /scripts/local/include/ncurses
done
cd /scripts/local/lib && ln -s libncurses.a libcurses.a