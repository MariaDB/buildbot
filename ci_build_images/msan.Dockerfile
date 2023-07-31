
# msan.Dockerfile
# this is to create images with MSAN for BB workers
WORKDIR /tmp/msan

ENV CC=clang-15
ENV CXX=clang++-15
ENV GDB_PATH=/msan-libs/bin/gdb
ENV MSAN_LIBDIR=/msan-libs
ENV MSAN_SYMBOLIZER_PATH=/msan-libs/bin/llvm-symbolizer-msan

ENV PATH=$MSAN_LIBDIR/bin:$PATH

RUN mkdir $MSAN_LIBDIR \
    && mkdir $MSAN_LIBDIR/bin \
    && printf '#!/bin/sh\nunset LD_LIBRARY_PATH\nexec llvm-symbolizer-15 "$@"' > $MSAN_SYMBOLIZER_PATH \
    && printf '#!/bin/sh\nunset LD_LIBRARY_PATH\nexec /usr/bin/gdb "$@"' > $GDB_PATH \
    && curl -sL https://apt.llvm.org/llvm-snapshot.gpg.key | gpg --dearmor -o /usr/share/keyrings/llvm-snapshot.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/llvm-snapshot.gpg] \
    http://apt.llvm.org/bullseye/ llvm-toolchain-bullseye-15 main" > /etc/apt/sources.list.d/llvm-toolchain.list \
    && echo "deb-src [signed-by=/usr/share/keyrings/llvm-snapshot.gpg] \
    http://apt.llvm.org/bullseye/ llvm-toolchain-bullseye-15 main" >> /etc/apt/sources.list.d/llvm-toolchain.list \
    && apt-get update \
    && apt-get -y install --no-install-recommends \
       clang-15 \
       libclang-rt-15-dev \
       libc++abi-15-dev \
       libc++-15-dev \
       llvm-15 \
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
        -DLLVM_USE_SANITIZER=MemoryWithOrigins \
    && make -C build -j "$(nproc)" \
    && cp -aL build/lib/libc++.so* $MSAN_LIBDIR \
    && cp -a build/include/c++/v1 "$MSAN_LIBDIR/include" \
    && rm $MSAN_LIBDIR/libc++.so \
    && ln -sf $MSAN_LIBDIR/libc++.so.1 $MSAN_LIBDIR/libc++.so \
    && rm -rf -- *

ENV CFLAGS="-fno-omit-frame-pointer -O2 -g -fsanitize=memory"
ENV CXXFLAGS="$CFLAGS"
ENV LDFLAGS="-fsanitize=memory"

RUN apt-get source gnutls28 \
    && mv gnutls28-*/* . \
    && mk-build-deps -it 'apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends --yes' \
    && aclocal \
    && automake --add-missing \
    && ./configure \
        --with-included-libtasn1 \
        --with-included-unistring \
        --without-p11-kit \
        --disable-hardware-acceleration \
        --disable-guile \
    && make -j "$(nproc)" \
    && cp -aL lib/.libs/libgnutls.so* $MSAN_LIBDIR \
    && rm -rf -- * \
    \
    && apt-get source nettle \
    && mv nettle-*/* . \
    && mk-build-deps -it 'apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends --yes' \
    && ./configure \
        --disable-assembler \
    && make -j "$(nproc)" \
    && cp -aL .lib/lib*.so* $MSAN_LIBDIR \
    && rm -rf -- * \
    \
    && apt-get source libidn2 \
    && mv libidn2-*/* . \
    && mk-build-deps -it 'apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends --yes' \
    && ./configure \
        --enable-valgrind-tests=no \
    && make -j "$(nproc)" \
    && cp -aL lib/.libs/libidn2.so* $MSAN_LIBDIR \
    && rm -rf -- * \
    \
    && apt-get source gmp \
    && mv gmp-*/* . \
    && mk-build-deps -it 'apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends --yes' \
    && ./configure \
        --disable-assembly \
    && make -j "$(nproc)" \
    && cp -aL .libs/libgmp.so* $MSAN_LIBDIR \
    && rm -rf -- *

ENV CFLAGS="$CFLAGS -Wno-conversion"
ENV CXXFLAGS="$CFLAGS"

RUN apt-get source cracklib2 \
    && mv cracklib2-*/* . \
    && mk-build-deps -it 'apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends --yes' \
    && ./configure \
        --with-default-dict=/usr/share/dict/cracklib-small \
    && make -j "$(nproc)" \
    && make install \
    && create-cracklib-dict ./dicts/cracklib-small \
    && cp -aL lib/.libs/*.so* $MSAN_LIBDIR \
    && rm -rf -- * \
    && rm -rf /tmp/msan \
    && apt-get clean \
    && apt-get -y purge \
       bzip2 \
       libbz2-dev \
       liblz4-dev \
       liblzma-dev \
       liblzo2-dev \
       libsnappy-dev \
    && chmod -R a+x $MSAN_LIBDIR/bin/*

ENV CFLAGS="-fno-omit-frame-pointer -O2 -g -fsanitize=memory"
ENV CXXFLAGS="$CFLAGS"
