# Builds latest rr into msan image for ease of use for developers
# and MariaDB build dependencies

ARG BASE_IMAGE
FROM "$BASE_IMAGE" as rr
LABEL maintainer="MariaDB Buildbot maintainers"
ENV CARGO_NET_GIT_FETCH_WITH_CLI=true

# This will make apt-get install without question
ENV DEBIAN_FRONTEND=noninteractive

# hadolint ignore=DL3003
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
      ca-certificates \
      capnproto \
      cmake \
      curl \
      g++ \
      g++-multilib \
      gdb \
      libcapnp-dev \
      libzstd-dev \
      lldb \
      make \
      pkg-config \
      python3-pexpect \
      unzip \
      zlib1g-dev \
    && curl https://codeload.github.com/rr-debugger/rr/zip/refs/heads/master -o master.zip \
    && unzip master.zip \
    && rm master.zip \
    && mkdir -p build \
    && cd build \
    && cmake -DCMAKE_PREFIX=/usr ../rr-master \
    && cmake --build . --parallel 12 \
    && cmake --install . --prefix /tmp/install/usr \
    && apt-get purge -y \
      ca-certificates \
      capnproto \
      cmake \
      curl \
      g++ \
      g++-multilib \
      gdb \
      libcapnp-dev \
      libzstd-dev \
      lldb \
      make \
      pkg-config \
      python3-pexpect \
      unzip \
      zlib1g-dev \
    && cd .. \
    && rm -rf build rr-master
