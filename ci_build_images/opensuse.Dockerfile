#
# Buildbot worker for building MariaDB
#
# Provides a base OpenSUSE image with latest buildbot worker installed
# and MariaDB build dependencies

ARG BASE_IMAGE
FROM "$BASE_IMAGE"
LABEL maintainer="MariaDB Buildbot maintainers"

COPY --chmod=755 mariadb_zypper_expect /
# Install updates and required packages
RUN zypper update -y \
    && zypper install -y -t pattern devel_basis \
    && source /etc/os-release \
    && VERSION_ID=${VERSION_ID%%.*} \
    && ARCH=$(rpm --query --queryformat='%{ARCH}' zypper) \
    && if [ "$ARCH" = x86_64 ]; then ARCH=amd64 ; fi \
    && zypper addrepo https://ci.mariadb.org/galera/mariadb-4.x-latest-gal-"${ARCH}-${ID%%-leap}-${VERSION_ID}".repo \
    && zypper install -y \
    bzip2 \
    ccache \
    check-devel \
    checkpolicy \
    cmake \
    cracklib-devel \
    createrepo_c \
    curl \
    expect \
    fmt-devel \
    galera-4 \
    gcc-c++ \
    git \
    glibc-locale \
    jemalloc-devel \
    libaio-devel \
    libboost_filesystem1_75_0-devel \
    libboost_program_options1_75_0-devel \
    libboost_system1_75_0-devel \
    libbz2-devel \
    libcurl-devel \
    libffi-devel \
    libgnutls-devel \
    liblz4-devel \
    libopenssl-3-devel \
    liburing2-devel \
    libxml2-devel \
    pam-devel \
    pcre2-devel \
    perl-Net-SSLeay \
    policycoreutils \
    python312-devel \
    python312-pip \
    rpm-build \
    rpmlint \
    snappy-devel \
    subversion \
    systemd-devel \
    wget \
    && ./mariadb_zypper_expect \
    && zypper clean -a \
    && curl -sLo /usr/local/bin/dumb-init "https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_$(uname -m)" \
    && chmod +x /usr/local/bin/dumb-init


ENV WSREP_PROVIDER=/usr/lib64/galera-4/libgalera_smm.so
