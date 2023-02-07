RUN apt-get -y --no-install-recommends install \
      apt-utils \
      dpatch \
      libevent-dev \
      valgrind

ENV CLANG=12
ENV MSAN_LIBDIR=/msan-libs
ENV CC=clang-$CLANG CXX=clang++-$CLANG

WORKDIR /tmp/build
RUN apt-get install -y --no-install-recommends \
      clang-$CLANG \
      libc++-$CLANG-dev \
      libc++abi-$CLANG-dev \
      pkg-config \
      libunwind8-dev \
    && apt-get source \
      cracklib2 \
      gmp \
      gnutls28 \
      libidn2 \
      nettle \
      llvm-toolchain-$CLANG \
    && apt-get clean

# hadolint ignore=DL3003
RUN cd llvm-toolchain-$CLANG-$CLANG.*/ \
    && mkdir libc++msan \
    && cd libc++msan \
    && cmake ../libcxx -DCMAKE_BUILD_TYPE=RelWithDebInfo -DLLVM_USE_SANITIZER=Memory \
    && cmake --build . -- -j"$(nproc)"

ENV CFLAGS="-fno-omit-frame-pointer -O2 -g -fsanitize=memory"
ENV CXXFLAGS="$CFLAGS"
ENV LDFLAGS=-fsanitize=memory

WORKDIR /tmp/build
# hadolint ignore=DL3003
RUN cd gnutls28-*/ \
    && aclocal \
    && automake --add-missing \
    && ./configure --with-included-libtasn1 \
      --with-included-unistring \
      --without-p11-kit \
      --disable-hardware-acceleration \
      --with-libnettle-prefix=/usr \
    && make -j"$(nproc)"

WORKDIR /tmp/build
# hadolint ignore=DL3003
RUN cd nettle-*/ \
    && ./configure --disable-assembler \
    && make -j"$(nproc)" \
    && cd .. \
    && cd libidn2-*/ \
    && ./configure --enable-valgrind-tests=no \
    && make -j"$(nproc)"

WORKDIR /tmp/build
# hadolint ignore=DL3003
RUN cd gmp-*/ \
    && ./configure --disable-assembly \
    && make -j"$(nproc)"

WORKDIR /tmp/build
# hadolint ignore=DL3003
RUN cd cracklib2-*/ \
    && ./configure --with-default-dict=/usr/share/dict/cracklib-small \
    && make -j"$(nproc)" \
    && make install \
    && create-cracklib-dict /tmp/build/cracklib*/dicts/cracklib-small

WORKDIR /tmp/build
RUN mkdir /msan-libs \
    && cp -aL llvm-toolchain-$CLANG-$CLANG*/libc++msan/lib/libc++.so* \
      gnutls28-*/lib/.libs/libgnutls.so* \
      nettle-*/.lib/lib*.so* \
      gmp-*/.libs/libgmp.so* \
      libidn2-*/lib/.libs/libidn2.so \
      cracklib2*/lib/.libs/*.so* \
      "$MSAN_LIBDIR"

RUN apt-get purge -y \
      liblz4-dev \
      liblzma-dev \
      libsnappy-dev \
    && apt-get clean
