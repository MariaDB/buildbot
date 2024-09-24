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

WORKDIR /

# For convenience of human users of msan image
ENV MSAN_OPTIONS=abort_on_error=1:poison_in_dtor=0

# Clear from base image
ENV CFLAGS= CXXFLAGS=

ENV CMAKE_GENERATOR=Ninja
RUN . /etc/os-release \
    apt-get install --no-install-recommends -y ninja-build; \
    && apt-get clean
