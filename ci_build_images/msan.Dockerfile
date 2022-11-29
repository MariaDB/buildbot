# this is to create images with MSAN for BB workers
WORKDIR /tmp/msan

ENV MSAN_LIBDIR=/msan-libs

RUN mkdir $MSAN_LIBDIR \
    && curl -sL https://apt.llvm.org/llvm-snapshot.gpg.key | gpg --dearmor -o /usr/share/keyrings/llvm-snapshot.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/llvm-snapshot.gpg] \
    http://apt.llvm.org/jammy/ llvm-toolchain-jammy-15 main" > /etc/apt/sources.list.d/llvm-toolchain.list \
    && echo "deb-src [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/llvm-snapshot.gpg] \
    http://apt.llvm.org/jammy/ llvm-toolchain-jammy-15 main" >> /etc/apt/sources.list.d/llvm-toolchain.list \
    && apt-get update \
    && apt-get -y install --no-install-recommends clang-15 \
    && apt-get source libc++-15-dev \
    && mv llvm-toolchain-15-15*/* . \
    && mkdir build \
    && cmake \
        -S runtimes \
        -B build \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_C_COMPILER=clang-15 \
        -DCMAKE_CXX_COMPILER=clang++-15 \
        -DLLVM_ENABLE_RUNTIMES="libcxx;libcxxabi" \
        -DLLVM_USE_SANITIZER=Memory \
    && make -C build install -j "$(nproc)" \
    && cp -aL build/lib/libc++.so* $MSAN_LIBDIR \
    && find . -mindepth 1 -maxdepth 1 -exec rm -rf {} \; \
    \
    && apt-get source gnutls28 \
    && mv gnutls28-*/* . \
    && mk-build-deps -it 'apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends --yes' \
    && aclocal \
    && automake --add-missing \
    && ./configure \
        --with-included-libtasn1 \
        --with-included-unistring \
	    --without-p11-kit \
        --disable-hardware-acceleration \
        -with-libnettle-prefix=/usr \
    && make -j "$(nproc)" \
    && cp -aL lib/.libs/libgnutls.so* $MSAN_LIBDIR \
    && find . -mindepth 1 -maxdepth 1 -exec rm -rf {} \; \
    \
    && apt-get source nettle \
    && mv nettle-*/* . \
    && mk-build-deps -it 'apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends --yes' \
    && ./configure \
        --disable-assembler \
    && make -j "$(nproc)" \
    && cp -aL .lib/lib*.so* $MSAN_LIBDIR \
    && find . -mindepth 1 -maxdepth 1 -exec rm -rf {} \; \
    \
    && apt-get source libidn2 \
    && mv libidn2-*/* . \
    && mk-build-deps -it 'apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends --yes' \
    && ./configure \
        --enable-valgrind-tests=no \
    && make -j "$(nproc)" \
    && cp -aL lib/.libs/libidn2.so* $MSAN_LIBDIR \
    && find . -mindepth 1 -maxdepth 1 -exec rm -rf {} \; \
    \
    && apt-get source gmp \
    && mv gmp-*/* . \
    && mk-build-deps -it 'apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends --yes' \
    && ./configure \
        --disable-assembly \
    && make -j "$(nproc)" \
    && cp -aL .libs/libgmp.so* $MSAN_LIBDIR \
    && find . -mindepth 1 -maxdepth 1 -exec rm -rf {} \; \
    \
    && apt-get source cracklib2 \
    && mv cracklib2-*/* . \
    && mk-build-deps -it 'apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends --yes' \
    && ./configure \
        --with-default-dict=/usr/share/dict/cracklib-small \
    && make -j "$(nproc)" \
    && make install \
    && create-cracklib-dict ./dicts/cracklib-small \
    && cp -aL lib/.libs/*.so* $MSAN_LIBDIR \
    && find . -mindepth 1 -maxdepth 1 -exec rm -rf {} \; \
    \
    && apt-get clean
