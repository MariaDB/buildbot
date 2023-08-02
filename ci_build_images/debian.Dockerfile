# Buildbot worker for building MariaDB
#
# Provides a base Debian/Ubuntu image with latest buildbot worker installed
# and MariaDB build dependencies

ARG base_image
FROM "$base_image"
ARG mariadb_branch=11.1
LABEL maintainer="MariaDB Buildbot maintainers"
ENV CARGO_NET_GIT_FETCH_WITH_CLI=true

# This will make apt-get install without question
ARG DEBIAN_FRONTEND=noninteractive

# Enable apt sources
RUN if [ -f /etc/apt/sources.list ]; then \
      sed 's/^deb /deb-src /g' /etc/apt/sources.list >/etc/apt/sources.list.d/debian-sources.list; \
    fi \
    # see man 5 sources.list (DEB822-STYLE FORMAT) \
    && if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's/Types: deb/Types: deb deb-src/g' /etc/apt/sources.list.d/debian.sources; \
    fi

# Install updates and required packages
# see: https://cryptography.io/en/latest/installation/
RUN . /etc/os-release; \
    apt-get update \
    && apt-get -y upgrade \
    && apt-get -y install --no-install-recommends curl ca-certificates devscripts equivs lsb-release \
    && echo "deb [trusted=yes] https://buildbot.mariadb.net/archive/builds/mariadb-4.x/latest/kvm-deb-${VERSION_CODENAME}-$(dpkg --print-architecture)-gal/debs ./" > /etc/apt/sources.list.d/galera-4.list \
    && sed -i -e s/arm64/aarch64/ -e s/ppc64el/ppc64le/ /etc/apt/sources.list.d/galera-4.list \
    && if [ "${VERSION_CODENAME}" = lunar ] && [ "$(dpkg --print-architecture)" = arm64 ]; then rm /etc/apt/sources.list.d/galera-4.list; fi \
    && if [ "${VERSION_CODENAME}" = bookworm ] || [ "${VERSION_CODENAME}" = mantic ] || [ "$(getconf LONG_BIT)" = 32 ]; then rm /etc/apt/sources.list.d/galera-4.list; fi \
    && apt-get update \
    && curl -skO https://raw.githubusercontent.com/MariaDB/server/44e4b93316be8df130c6d87880da3500d83dbe10/debian/control \
    && mkdir debian \
    && mv control debian/control \
    && touch debian/rules VERSION debian/not-installed \
    && curl -skO https://raw.githubusercontent.com/MariaDB/server/$mariadb_branch/debian/autobake-deb.sh \
    && chmod a+x autobake-deb.sh \
    && AUTOBAKE_PREP_CONTROL_RULES_ONLY=1 ./autobake-deb.sh \
    && mk-build-deps -r -i debian/control \
    -t 'apt-get -y -o Debug::pkgProblemResolver=yes --no-install-recommends' \
    && apt-get -y build-dep -q mariadb-server \
    && apt-get -y install --no-install-recommends \
    build-essential \
    ccache \
    check \
    default-jdk-headless \
    dumb-init \
    gawk \
    git \
    gnutls-dev \
    iproute2 \
    iputils-ping \
    libasio-dev \
    libboost-dev \
    libboost-filesystem-dev \
    libboost-program-options-dev \
    libdbi-perl \
    libffi-dev \
    libssl-dev \
    lsof \
    python3-buildbot-worker \
    python3-dev \
    python3-setuptools \
    rsync \
    scons \
    socat \
    sudo  \
    wget \
    && if [ "$(getconf LONG_BIT)" = 64 ]; then \
      apt-get -y install --no-install-recommends galera-4; \
    fi \
    && if ! grep -q 'bionic' /etc/apt/sources.list; then \
      apt-get -y install --no-install-recommends flex; \
    fi \
    && if ! grep -q 'jammy' /etc/apt/sources.list; then \
      apt-get -y install --no-install-recommends clang-14; \
    fi \
    && apt-get clean

ENV WSREP_PROVIDER=/usr/lib/galera/libgalera_smm.so
