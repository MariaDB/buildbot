#!/bin/bash
# shellcheck disable=SC2086

#------------------------------------------------------------------------------

### The code below does not work because, nowadays,
# GnuTLS require static gmp, nettle libraries

# yumdownloader --source gnutls-devel
# yum-builddep -y gnutls-*.src.rpm
# rpm -ivh gnutls-*.src.rpm
# sed -i 's/--disable-static/--enable-static \\\n--disable-tests/g' ~/rpmbuild/SPECS/gnutls.spec
# sed -i 's/export LDFLAGS="-Wl,--no-add-needed"/export LDFLAGS="-Wl,--copy-dt-needed-entries -fpic -fPIC"/g' ~/rpmbuild/SPECS/gnutls.spec
# sed -i 's/make %{?_smp_mflags}/make %{?_smp_mflags} CFLAGS="-fpic -fPIC" CXX_FLAGS="-fpic -fPIC"/g' ~/rpmbuild/SPECS/gnutls.spec
# rpmbuild -bc ~/rpmbuild/SPECS/gnutls.spec
# mv -v ~/rpmbuild/BUILD/gnutls-*/lib/.libs/libgnutls.a local/lib
# rm -rf ~/rpmbuild gnutls-*.src.rpm


###
# I tried to build Nettle statically from distro .src.rpm but
# the version on almalinux-8 is buggy and, during build, it will raise an OOM
# on my machine, consuming all available RAM/SWAP.

# Using a newer Nettle works but GnuTLS .src.rpm from distro won't compile
# with an upgraded version of Nettle
# This is why I use custom versions for everything.
# These versions are actually what dbart used for updating GnuTLS on buildbot.mariadb.net


### When I say it does not work, during server compilation,
# with the << from .src.rpm. >> method you will find errors like:

#/scripts/local/lib/libgnutls.a(lt12-cipher.o):(.data.rel.ro+0x3b8): undefined reference to `nettle_gcm_camellia128_set_iv'
#/scripts/local/lib/libgnutls.a(lt15-pk.o): In function `_wrap_nettle_pk_decrypt':

#------------------------------------------------------------------------------

set -e

### Install build-dependencies for GMP/NETTLE/GNUTLS.
# Not perfect, these are the build-deps for the distro versions but it works.

## Download src rpms
yumdownloader --source gmp-devel
yumdownloader --source nettle-devel
yumdownloader --source gnutls-devel

## Install build deps
yum-builddep -y gmp-*.src.rpm
yum-builddep -y nettle-*.src.rpm
yum-builddep -y gnutls-*.src.rpm

### Download custom versions for GMP/NETTLE/GNUTLS
cd $HOME
find /usr/local -type f >old

v_gmp='6.2.1' ; url_gmp='ftp://ftp.gnu.org/gnu/gmp'
file_gmp="gmp-${v_gmp}.tar.bz2"
wget ${url_gmp}/${file_gmp} && tar -xf ${file_gmp}

v_nettle='3.7.2' ; url_nettle='ftp://ftp.gnu.org/gnu/nettle'
file_nettle="nettle-${v_nettle}.tar.gz"
wget ${url_nettle}/${file_nettle} && tar -xf ${file_nettle}

v_gnutls='3.7' ; v_gnutls_m='11' ; url_gnutls='https://www.gnupg.org/ftp/gcrypt/gnutls'
file_gnutls="gnutls-${v_gnutls}.${v_gnutls_m}.tar.xz" ;
wget ${url_gnutls}/v${v_gnutls}/${file_gnutls} && tar -xf ${file_gnutls}

rm -f ./*.tar.*

### Compile the libraries

## GMP
cd $HOME/gmp-*
export LDFLAGS='-fpic -fPIC'
export CFLAGS='-fpic -fPIC -DPIC'
export CXXFLAGS='-fpic -fPIC'
./configure --prefix=$HOME/a --disable-shared --enable-static
make -j"$(nproc)"
make install

## NETTLE
cd $HOME/nettle-*
export LDFLAGS="-L$HOME/a/lib -fpic -fPIC"
export CFLAGS="-I$HOME/a/include -fpic -fPIC"
export CXXFLAGS="-I$HOME/a/include -fpic -fPIC"
./configure --prefix=$HOME/a --libdir=$HOME/a/lib --disable-shared --enable-static
make -j"$(nproc)" SUBDIRS=tools
make install

## GNUTLS
cd $HOME/gnutls-*
export PKG_CONFIG_PATH=$HOME/a/lib/pkgconfig
export LDFLAGS="-L$HOME/a/lib -fpic -fPIC"
export CFLAGS="-I$HOME/a/include -fpic -fPIC"
export CXXFLAGS="-I$HOME/a/include -fpic -fPIC"
./configure --disable-shared --enable-static --disable-doc --disable-tests --disable-cxx --disable-openssl-compatibility --with-included-libtasn1 --with-included-unistring --without-p11-kit --without-idn --without-zstd
make -j"$(nproc)"
make install

### Install GnuTLS library under /usr/local/lib
cd ${HOME}
mkdir -v gmp gnutls nettle hogweed
(set -x;cd gmp && ar x ~/a/lib/libgmp.a)
(set -x;cd nettle && ar x ~/a/lib/libnettle.a)
(set -x;cd hogweed && ar x ~/a/lib/libhogweed.a)
(set -x;cd gnutls && ar x /usr/local/lib/libgnutls.a)
ar r libgnutls.a {gmp,gnutls,nettle,hogweed}/*
ranlib libgnutls.a
rm -v /usr/local/lib/libgnutls.*
cp -v libgnutls.a /usr/local/lib/

### Prepare tarball
touch /usr/local/gnutls.files
diff -e old <(find /usr/local/ -type f)|grep /|sort > gnutls.files
cp gnutls.files /usr/local/
tar -cvjf gnutlsa.tar.bz2 -T /usr/local/gnutls.files
