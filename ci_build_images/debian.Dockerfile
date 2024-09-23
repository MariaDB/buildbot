# Buildbot worker for building MariaDB
#
# Provides a base Debian/Ubuntu image with latest buildbot worker installed
# and MariaDB build dependencies

ARG BASE_IMAGE
FROM "$BASE_IMAGE"
ARG MARIADB_BRANCH=11.1
LABEL maintainer="MariaDB Buildbot maintainers"
ENV CARGO_NET_GIT_FETCH_WITH_CLI=true

# This will make apt-get install without question
ARG DEBIAN_FRONTEND=noninteractive

# Enable apt sources
RUN . /etc/os-release \
    && if [ -f "/etc/apt/sources.list.d/$ID.sources" ]; then \
      sed -i 's/Types: deb/Types: deb deb-src/g' "/etc/apt/sources.list.d/$ID.sources"; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed 's/^deb /deb-src /g' /etc/apt/sources.list >"/etc/apt/sources.list.d/$ID-sources.list"; \
    else \
      echo "ERROR: can't find apt repo configuration file"; \
      exit 1; \
    fi

# Install updates and required packages
# see: https://cryptography.io/en/latest/installation/
RUN . /etc/os-release \
    && apt-get update \
    && apt-get -y upgrade \
    && apt-get -y install --no-install-recommends \
    ca-certificates \
    curl \
    devscripts  \
    equivs  \
    lsb-release \
    && if [ "${VERSION_ID}" = "20.04" ]; then apt-get -y install --no-install-recommends g++-10; fi \
    && if [ "$(arch)" = "x86_64" ]; then ARCH="amd64"; else ARCH=$(arch); echo /* galera-4 */; fi \
    && if curl --head --silent "https://ci.mariadb.org/galera/mariadb-4.x-latest-gal-${ARCH}-${ID}-$(echo "$VERSION_ID" | sed 's/\.//').sources" | head -n1 | grep -q 200; then \
      curl -s "https://ci.mariadb.org/galera/mariadb-4.x-latest-gal-${ARCH}-${ID}-$(echo "$VERSION_ID" | sed 's/\.//').sources" >/etc/apt/sources.list.d/galera-4.sources; fi \
    && apt-get update \
    && curl -skO "https://raw.githubusercontent.com/MariaDB/server/$MARIADB_BRANCH/debian/control" \
    && mkdir debian \
    && mv control debian/control \
    && touch debian/rules VERSION debian/not-installed \
    && curl -skO "https://raw.githubusercontent.com/MariaDB/server/$MARIADB_BRANCH/debian/autobake-deb.sh" \
    && chmod a+x autobake-deb.sh \
    && AUTOBAKE_PREP_CONTROL_RULES_ONLY=1 ./autobake-deb.sh \
    && mk-build-deps -r -i debian/control \
    -t 'apt-get -y -o Debug::pkgProblemResolver=yes --no-install-recommends' \
    && apt-get -y build-dep -q mariadb-server \
    && apt-get -y install --no-install-recommends \
    apt-utils \
    build-essential \
    buildbot-worker \
    bzip2 \
    ccache \
    check \
    default-jdk\
    dumb-init \
    gawk \
    gdb \
    git \
    gnutls-dev \
    iproute2 \
    iputils-ping \
    libasio-dev \
    libboost-dev \
    libboost-filesystem-dev \
    libboost-program-options-dev \
    libbz2-dev \
    libdbi-perl \
    libeigen3-dev \
    libffi-dev \
    libio-socket-ssl-perl \
    libnet-ssleay-perl \
    libssl-dev \
    lsof \
    python3-dev \
    python3-setuptools \
    rsync \
    socat \
    sudo  \
    wget \
    && if [ "$(getconf LONG_BIT)" = 64 ]; then apt-get -y install --no-install-recommends galera-4; fi \
    && if [ "${VERSION_ID}" != 18.04 ]; then \
      apt-get -y install --no-install-recommends flex; \
    fi \
    && if [ "${VERSION_ID}" = 22.04 ]; then \
      apt-get -y install --no-install-recommends clang-14 libpcre3-dev llvm; \
    elif [ "${VERSION_ID}" = 24.04 ]; then \
      # https://packages.ubuntu.com/noble/libclang-rt-18-dev, provider of asan, needs 32bit deps for amd64 \
      if [ "$(arch)" = "x86_64" ]; then dpkg --add-architecture i386 && apt-get update; fi \
      && apt-get -y install --no-install-recommends clang llvm-dev libclang-rt-18-dev; \
    fi \
    && apt-get clean

ENV WSREP_PROVIDER=/usr/lib/galera/libgalera_smm.so

# Prevent debian sid runtime error
ENV CRYPTOGRAPHY_OPENSSL_NO_LEGACY=1
