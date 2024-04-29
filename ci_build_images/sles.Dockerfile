#
# Buildbot worker for building MariaDB
#
# Provides a base SLES image with latest buildbot worker installed
# and MariaDB build dependencies

ARG BASE_IMAGE
FROM "$BASE_IMAGE"
LABEL maintainer="MariaDB Buildbot maintainers"

# Install updates and required packages
RUN zypper -n update \
    && zypper -n install -t pattern devel_basis \
    && zypper -n install \
    bzip2 \
    ccache \
    check-devel \
    cracklib-devel \
    git \
    glibc-locale \
    jemalloc-devel \
    libboost_filesystem1_66_0-devel \
    libboost_program_options1_66_0-devel \
    libboost_system1_66_0-devel \
    libcurl-devel \
    libffi-devel \
    libgnutls-devel \
    perl-Net-SSLeay \
    policycoreutils \
    python3-devel \
    python3-pip \
    rpm-build \
    rpmlint \
    snappy-devel \
    subversion \
    wget \
    && zypper modifyrepo --enable SLE_BCI_source \
    && zypper -n install "https://ftp.lysator.liu.se/pub/opensuse/distribution/leap/15.5/repo/oss/$(arch)/judy-devel-1.0.5-1.2.$(arch).rpm" \
    && zypper -n source-install -d mariadb \
    && zypper clean -a \
    && curl -sLo /usr/local/bin/dumb-init "https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_$(uname -m)" \
    && chmod +x /usr/local/bin/dumb-init
