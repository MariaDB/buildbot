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
    && if [ "${VERSION_ID}" = "20.04" ]; then apt-get -y install --no-install-recommends g++-10; fi \
    && if [ "$(arch)" = "x86_64" ]; then ARCH="amd64"; else ARCH=$(arch); fi \
    && curl -s "https://ci.mariadb.org/galera/mariadb-4.x-latest-gal-${ARCH}-${ID}-$(echo "$VERSION_ID" | sed 's/\.//').sources" >/etc/apt/sources.list.d/galera-4.sources \
    # VERSION_ID=13 once released \
    && if [ "${VERSION_CODENAME}" = trixie ] || [ "$(getconf LONG_BIT)" = 32 ]; then rm /etc/apt/sources.list.d/galera-4.sources; fi \
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
    apt-utils \
    build-essential \
    bzip2 \
    ccache \
    check \
    default-jdk\
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
    libbz2-dev \
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
    && if [ "${VERSION_ID}" != 18.04 ]; then \
      apt-get -y install --no-install-recommends flex; \
    fi \
    && if [ "${VERSION_ID}" = 22.04 ]; then \
      apt-get -y install --no-install-recommends clang-14 libpcre3-dev llvm; \
    fi \
    # see: https://jira.mariadb.org/browse/MDBF-637 \
    && if [ "${VERSION_ID}" = 22.04 ] && [ "$(arch)" != s390x ]; then \
         case "$(arch)" in "x86_64") \
          deb_arch="amd64"; \
          ;; \
          "x86") \
          deb_arch="i386" \
          ;; \
          "aarch64") \
          deb_arch="arm64" \
          ;; \
          "ppc64le") \
          deb_arch="ppc64el" \
          ;; \
        esac; \
        reprepro_version="5.4.3-1"; \
        curl -skO "http://ftp.debian.org/debian/pool/main/r/reprepro/reprepro_${reprepro_version}_${deb_arch}.deb"; \
        apt-get install -y --no-install-recommends "./reprepro_${reprepro_version}_${deb_arch}.deb"; \
        rm -f "./reprepro_${reprepro_version}_${deb_arch}.deb"; \
      else \
        apt-get install -y --no-install-recommends reprepro; \
      fi \
    && apt-get clean

ENV WSREP_PROVIDER=/usr/lib/galera/libgalera_smm.so
