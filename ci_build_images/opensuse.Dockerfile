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
RUN zypper update -y && \
    zypper install -y -t pattern devel_basis && \
    zypper install -y \
    bzip2 \
    ccache \
    check-devel \
    cmake \
    cracklib-devel \
    createrepo_c \
    curl \
    expect \
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
    libfmt8 \
    libgnutls-devel \
    liblz4-devel \
    libopenssl-3-devel \
    liburing2-devel \
    libxml2-devel \
    pcre2-devel \
    perl-Net-SSLeay \
    policycoreutils \
    python312-devel \
    python312-pip \
    rpm-build \
    rpmlint \
    snappy-devel \
    subversion \
    wget \
    && ./mariadb_zypper_expect \
    && zypper clean -a \
    && curl -sLo /usr/local/bin/dumb-init "https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_$(uname -m)" \
    && chmod +x /usr/local/bin/dumb-init
