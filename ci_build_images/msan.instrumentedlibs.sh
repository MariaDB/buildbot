#!/bin/bash
# script to generate msan instrumented libraries from debian sources

# The general principle here is:
# 0. for all runtime dependencies of MariaDB
# 1. take the debian source file (for consistent library ABI compatibility)
# 2. install the build dependencies of that source library
# 3. Use the CFLAGS/CXXFLAGS/LDFLAGS from the environment to perform the msan instrumentation
# 4. roughly follow what's in the debian/rules, but minimize to just produce the shared library
# 5. move the build library to $MSAN_LIBDIR

# Based on invaluable build-msanX.sh scripts in MDEV-20377 by Marko.

set -o errexit
set -o nounset
set -o pipefail
set -o posix

# some things depend on OS version. Expose these env variable
# for ease of determination.
. /etc/os-release

# Env variables used in build
export CFLAGS="-fno-omit-frame-pointer -O2 -g -fsanitize=memory"
export CXXFLAGS="$CFLAGS"
export LDFLAGS="-fsanitize=memory"

# gnutls used by libmariadb
apt-get source gnutls28
mv gnutls28-*/* .
mk-build-deps -it 'apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends --yes'
aclocal
automake --add-missing
./configure \
 --with-included-libtasn1 \
 --with-included-unistring \
 --without-p11-kit \
 --disable-hardware-acceleration \
 --disable-guile
make -j "$(nproc)"
cp -aL lib/.libs/libgnutls.so* "$MSAN_LIBDIR"
rm -rf -- *

# From: https://jira.mariadb.org/browse/MDEV-20377?focusedCommentId=290259&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-290259
# In the current Debian Sid, apt source libnettle8 would fetch Nettle 3.9, while libnettle8t64 includes Nettle 3.10, which the libgnutls would be built against.
# Note: If Valgrind is installed, the configure script for Nettle 3.10 build may hit Valgrind bug 492255 (hang when trying to execute valgrind on an empty MemorySanitizer compiled program). You can send SIGKILL to the memcheck (or similar) process to work around that, or you can uninstall Valgrind before executing the build script.

# An uninstrumented nettle produces a fault like:
# #0  0x00007ffff7769c02 in ?? () from /lib/x86_64-linux-gnu/libnettle.so.8
# #1  0x00007ffff7769e0b in nettle_sha512_digest () from /lib/x86_64-linux-gnu/libnettle.so.8
# #2  0x00007ffff7e48e8a in wrap_nettle_hash_output (src_ctx=0xbcf74c967d490141, digest=0x713000000008, digestsize=140737488331568) at mac.c:843
# #3  0x00007ffff765ffbf in ma_hash (algorithm=6, buffer=0x701000000110 "foo", buffer_length=3, digest=0x7fffffffa2f0 "\367\366\363\367\377\177") at /home/marko/11.2/libmariadb/include/ma_crypt.h:151
apt-get source nettle
mv nettle-*/* .
mk-build-deps -it 'apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends --yes'
# native assembly isn't understood by the msan instrumentation when it performs initialization of memory
# resulting in the above trace.
./configure  --disable-assembler
make -j "$(nproc)"
cp -aL .lib/lib*.so* "$MSAN_LIBDIR"
rm -rf -- *

# LIBIDN2 - GNUTLS and openssl use this library so it needs to be instrumented too
#
apt-get source libidn2
mv libidn2-*/* .
mk-build-deps -it 'apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends --yes'
make -f debian/rules  execute_before_dh_auto_configure
./configure --enable-valgrind-tests=no --enable-doc=no
make -j "$(nproc)"
cp -aL lib/.libs/libidn2.so* "$MSAN_LIBDIR"
rm -rf -- *

# GMP - the maths library for gnutls
apt-get source gmp
mv gmp-*/* .
mk-build-deps -it 'apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends --yes'
# There where dependency problems with documentation, and we don't need the documentation
# so its removed.
sed -e '/^.*"doc\/Makefile".*/d;s/doc\/Makefile //;' -i.bak configure
sed -e 's/^\(SUBDIRS = .*\) doc$/\1/;' -i.bak Makefile.in
./configure --disable-assembly
make -j "$(nproc)"
cp -aL .libs/libgmp.so* "$MSAN_LIBDIR"
rm -rf -- *

# XML2 - MariaDB connect engine and Columnstore(?) uses this
apt-get source libxml2
mv libxml2-*/* .
aclocal
automake --add-missing
./configure  --without-python --without-docbook --with-icu
make -j "$(nproc)"
cp -aL .libs/libxml2.so* "$MSAN_LIBDIR"
rm -rf -- *

# Unixodbc used by MariaDB Connect engine.
if [ "${VERSION_CODENAME}" = trixie ]; then
  # additional dependency in later debian versions.
  # libltdl-dev - System independent dlopen wrapper for GNU libtool
  apt-get install --no-install-recommends -y libltdl-dev
fi
apt-get source unixodbc-dev
mv unixodbc-*/* .
libtoolize --force
aclocal
autoheader
autoconf
automake --add-missing
./configure --enable-fastvalidate  --with-pth=no --with-included-ltdl=no
make -j "$(nproc)"
mv ./DriverManager/.libs/libodbc.so* "$MSAN_LIBDIR"
rm -rf -- *

# libfmt -  used by server for SFORMAT function
# will be hit by mtr test main.func_sformat
apt-get source libfmt-dev
mv fmtlib-*/* .
mkdir build
cmake -DFMT_DOC=OFF -DFMT_TEST=OFF  -DBUILD_SHARED_LIBS=on  -DFMT_PEDANTIC=on -S . -B build
cmake --build build
mv build/libfmt.so* "$MSAN_LIBDIR"
rm -rf -- *

# openssl - used by tls connections and parsec authentication in the server
apt-get source libssl-dev
mv openssl-*/* .
# note no-asm and enable-msan were't option for less than clang-19, something about libxcrypt instrumentation for libcrypt
# intentional word splitting of CFLAGS
# shellcheck disable=SC2086
./Configure  shared no-idea no-mdc2 no-rc5 no-zlib no-ssl3 enable-unit-test no-ssl3-method enable-rfc3779 enable-cms no-capieng no-rdrand no-asm enable-msan $CFLAGS
make -j "$(nproc)" build_libs
mv ./*.so* "$MSAN_LIBDIR"
rm -rf -- *

# pcre used by server
apt-get source  libpcre2-dev
mv pcre2-*/* .
cmake -S . -B build/ -DBUILD_SHARED_LIBS=ON -DBUILD_STATIC_LIBS=OFF -DPCRE2_BUILD_TESTS=OFF -DPCRE2_SUPPORT_JIT=ON  -DCMAKE_C_FLAGS="${CFLAGS} -Dregcomp=PCRE2regcomp -Dregexec=PCRE2regexec -Dregerror=PCRE2regerror -Dregfree=PCRE2regfree"
cmake --build build/
mv ./build/libpcre2*so* "$MSAN_LIBDIR"
rm -rf -- *

# cppunit used by galera
# intend to reuse this image for galera testing
apt-get source cppunit
mv cppunit-*/* .
./configure
make -j "$(nproc)"
mv ./src/cppunit/.libs/libcppunit.so* "$MSAN_LIBDIR"
rm -rf -- *

apt-get install --no-install-recommends -y libcppunit-dev
apt-get source subunit
mv subunit-*/* .
autoreconf  -vi
./configure
make libsubunit.la
mv .libs/libsubunit.so* "$MSAN_LIBDIR"
rm -rf -- *

# cracklib used by mariadb-plugin-cracklib-password-check
apt-get source cracklib2
mv cracklib2-*/* .
mk-build-deps -it 'apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends --yes'
aclocal
libtoolize
automake --add-missing
autoreconf
CFLAGS="$CFLAGS -Wno-error=int-conversion" ./configure --without-python \
 --with-default-dict=/usr/share/dict/cracklib-small
make -j "$(nproc)"
cp -aL lib/.libs/*.so* "$MSAN_LIBDIR"
rm -rf -- *
# MTR tests plugins.two_password_validations and plugins.cracklib_password_check
# indirectly via the shared lib attempt to access the packed version of this library

# This isn't overriding the file that its reading.
# shellcheck disable=SC2094
/usr/sbin/cracklib-packer /usr/share/dict/cracklib-small < /usr/share/dict/cracklib-small


# Now that we are built, clear out all the temporary build dependencies
apt-get clean
apt-get -y purge \
       bzip2 \
       libbz2-dev \
       liblz4-dev \
       liblzma-dev \
       liblzo2-dev \
       libsnappy-dev

# all libraries have been saved - the builddir contents aren't needed
rm -rf /msan-build
