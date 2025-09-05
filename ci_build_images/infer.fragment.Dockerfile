## This is a fragment file, do not build it directly!

# This is a fragment to build the infer sanitizer

# not enough release/tags, so reverting to a git ref
ARG INFER_GIT_REF=c03d46293021e08a4e2c312996b3a0bac9b62da8

# hadolint ignore=DL3003
RUN apt-get update \
    && apt-get install -y --no-install-recommends opam clang libmpfr-dev libsqlite3-dev ninja-build jq \
    && apt-get clean \
    && git init src \
    && cd src \
    && git remote add origin https://github.com/facebook/infer.git \
    && git fetch --depth=1 origin $INFER_GIT_REF \
    && git checkout FETCH_HEAD \
    && ./facebook-clang-plugins/clang/src/prepare_clang_src.sh \
    && CC=clang CXX=clang++ ./facebook-clang-plugins/clang/setup.sh --ninja --sequential-link \
    && TMPDIR=/build INTERACTIVE=no ./build-infer.sh clang \
    && make install BUILD_MODE=opt \
    && cd /  \
    && rm -rf src
