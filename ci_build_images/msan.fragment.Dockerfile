## This is a fragment file, do not execute it directly!

# msan.fragment.Dockerfile
# this is to create images with MSAN for BB workers
ARG CLANG_VERSION=20

# earliest tested version known to work - 19

# This CLANG_DEV_VERSION is a marker to make it possible to build a msan builder
# from the nightly clang versions as they are in a differently name repositories.
# This maps to the https://apt.llvm.org/ under "development" branch version.
ENV CLANG_DEV_VERSION=21

WORKDIR /msan-build

ENV CC=clang
ENV CXX=clang++
ENV MSAN_LIBDIR=/msan-libs
ENV MSAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-${CLANG_VERSION}

ENV CFLAGS="-fno-omit-frame-pointer -O2 -g"
ENV CXXFLAGS="$CFLAGS"

# hadolint ignore=SC2046,DL3003
RUN . /etc/os-release \
    && export LLVM_ENABLE_RUNTIMES="libcxx;libcxxabi;libunwind" \
    && mkdir "$MSAN_LIBDIR" \
    && curl -sL https://apt.llvm.org/llvm-snapshot.gpg.key | gpg --dearmor -o /usr/share/keyrings/llvm-snapshot.gpg \
    && if [ "$VERSION_CODENAME" = trixie ]; then VERSION_CODENAME=unstable; LLVM_DEB=""; else LLVM_DEB="-$VERSION_CODENAME"; fi \
    && if [ "${CLANG_VERSION}" -ge "${CLANG_DEV_VERSION}" ]; then \
        LLVM_PKG="llvm-toolchain-snapshot" ; \
       else \
        LLVM_PKG="llvm-toolchain-${CLANG_VERSION}" ; \
        LLVM_DEB="${LLVM_DEB}-${CLANG_VERSION}"; fi \
    && LLVM_DIR="${LLVM_PKG}-${CLANG_VERSION}" \
    && for v in deb deb-src; do \
         echo "$v [signed-by=/usr/share/keyrings/llvm-snapshot.gpg] https://apt.llvm.org/${VERSION_CODENAME}/ llvm-toolchain${LLVM_DEB} main" >> /etc/apt/sources.list.d/llvm-toolchain.list; done \
    && apt-get update \
    && apt-get -y install --no-install-recommends \
       clang-${CLANG_VERSION} \
       libclang-rt-${CLANG_VERSION}-dev \
       libc++abi-${CLANG_VERSION}-dev \
       libc++-${CLANG_VERSION}-dev \
       llvm-${CLANG_VERSION} \
       automake \
    && apt-get -y install --no-install-recommends libclang-${CLANG_VERSION}-dev libllvmlibc-${CLANG_VERSION}-dev \
    && update-alternatives \
        --verbose \
        --install /usr/bin/clang   clang   /usr/bin/clang-"${CLANG_VERSION}" 20 \
        --slave   /usr/bin/clang++ clang++ /usr/bin/clang++-"${CLANG_VERSION}" \
    && apt-get source "${LLVM_PKG}" \
    && mkdir -p ll-build \
    && cd ll-build \
    && cmake -S ../"$LLVM_DIR"*/runtimes \
        -DCMAKE_BUILD_TYPE=Release \
        -DLLVM_ENABLE_RUNTIMES="${LLVM_ENABLE_RUNTIMES}" \
        -DLLVM_INCLUDE_TESTS=OFF -DLLVM_INCLUDE_DOCS=OFF -DLLVM_ENABLE_SPHINX=OFF \
        -DLLVM_USE_SANITIZER=MemoryWithOrigins \
    && cmake --build . --target cxx --target cxxabi --parallel "$(nproc)" \
    && cp -aL lib/lib*.so* "$MSAN_LIBDIR" \
    && cp -a include/c++/v1 "$MSAN_LIBDIR/include" \
    && cd .. \
    && rm -rf -- *

RUN for f in "$MSAN_LIBDIR"/libunwind*; do mv "$f" "$f"-disable; done
# libunwrap move/disable because of https://github.com/llvm/llvm-project/issues/128621

COPY msan.instrumentedlibs.sh /msan-build
RUN ./msan.instrumentedlibs.sh

WORKDIR /

# For convenience of human users of msan image
ENV MSAN_OPTIONS=abort_on_error=1:poison_in_dtor=0

# Clear from base image
ENV CFLAGS= CXXFLAGS=

ENV CMAKE_GENERATOR=Ninja
# rr installation and its libcapnp version + ninja
RUN . /etc/os-release \
    && if [ "${VERSION_CODENAME}" = "trixie" ]; then \
         apt-get install --no-install-recommends -y libcapnp-1.1.0 ninja-build; \
       elif [ "${VERSION_CODENAME}" = "bullseye" ]; then \
         apt-get install --no-install-recommends -y libcapnp-0.7.0 ninja-build; \
       else \
         apt-get install --no-install-recommends -y libcapnp-0.9.2 ninja-build; \
    fi \
    && apt-get clean

# unknown rr
# hadolint ignore=DL3022
COPY --from=rr /tmp/install/usr/ /usr/

# ASAN/UBSAN
RUN echo "cat /etc/motd" > ~buildbot/.bashrc ; \
    printf "\
This is a container for ASAN, UBSAN and MSAN building\n\
\n\
A basic MSAN build can be achieved with\n\
\n\
cmake -DWITH_EMBEDDED_SERVER=OFF \\ \n\
      -DWITH_INNODB_{BZIP2,LZ4,LZMA,LZO,SNAPPY}=OFF \\ \n\
      -DPLUGIN_{MROONGA,ROCKSDB,OQGRAPH,SPIDER}=NO  \\ \n\
      -DWITH_ZLIB=bundled  \\ \n\
      -DHAVE_LIBAIO_H=0    \\ \n\
      -DCMAKE_DISABLE_FIND_PACKAGE_{URING,LIBAIO}=1  \\ \n\
      -DWITH_NUMA=NO  \\ \n\
      -DWITH_SYSTEMD=no \\ \n\
      -DWITH_MSAN=ON  \\ \n\
      -DHAVE_CXX_NEW=1  \\ \n\
      -DCMAKE_{EXE,MODULE}_LINKER_FLAGS=\"-L\${MSAN_LIBDIR} -Wl,-rpath=\${MSAN_LIBDIR}\" \\ \n\
      -DWITH_DBUG_TRACE=OFF \\ \n\
      /source\n\
\n\
A basic combined UBSAN/ASAN build can be achieved with\n\
\n\
cmake -DWITH_ASAN=ON -DWITH_ASAN_SCOPED=ON -DWITH_UBSAN=ON -DPLUGIN_PERFSCHEMA=NO /source\n\
\n\
Build with:\n\
\n\
cmake --build .\n\
\n\
Test with:\n\
\n\
mysql-test/mtr --parallel=auto\n\
\n\
There are UBSAN filters covering currently unfixed bugs within\n\
the server that can be used to direct your development, or validate if a\n\
observed failure is known. Perform the following to download/inspect them.\n\
\n\
curl https://raw.githubusercontent.com/mariadb-corporation/mariadb-qa/refs/heads/master/UBSAN.filter -o /build/UBSAN.filter\n\
\n\
After this, add suppressions to UBSAN_OPTIONS with\n\
\n\
export UBSAN_OPTIONS=\$UBSAN_OPTIONS:suppressions=/build/UBSAN.filter\n\
\n\
ref sanitizer flags documents:\n\
* https://github.com/google/sanitizers/wiki/AddressSanitizerFlags\n\
* https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html\n\n" > /etc/motd

ENV ASAN_OPTIONS=quarantine_size_mb=512:atexit=0:detect_invalid_pointer_pairs=3:dump_instruction_bytes=1:allocator_may_return_null=1
ENV UBSAN_OPTIONS=print_stacktrace=1:report_error_type=1
ENV MTR_PARALLEL=auto
