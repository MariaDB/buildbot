# Buildbot worker for building MariaDB
#
# Provides a base Debian/Ubuntu image with latest buildbot worker installed
# and MariaDB build dependencies

ARG base_image
FROM "$base_image"
ARG mariadb_branch=10.7
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
RUN apt-get update \
    && apt-get -y upgrade \
    && apt-get -y install --no-install-recommends curl ca-certificates devscripts equivs lsb-release \
    && curl -skO https://raw.githubusercontent.com/MariaDB/server/$mariadb_branch/debian/control \
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
    dumb-init \
    gawk \
    git \
    gnutls-dev \
    iputils-ping \
    libasio-dev \
    libboost-dev \
    libboost-filesystem-dev \
    libboost-program-options-dev \
    libffi-dev \
    libssl-dev \
    lintian \
    python3-dev \
    python3-setuptools \
    scons \
    sudo  \
    wget \
    && if ! grep -q 'stretch' /etc/apt/sources.list; then \
      apt-get -y install --no-install-recommends python3-buildbot-worker; \
    fi \
    # install Debian 9 only deps \
    && if grep -q 'stretch' /etc/apt/sources.list; then \
        apt-get -y install --no-install-recommends python3-pip; \
    fi \
    && apt-get clean
