#
# Buildbot worker for building MariaDB
#
# Provides a base OpenSUSE image with latest buildbot worker installed
# and MariaDB build dependencies

ARG base_image
FROM "$base_image"
LABEL maintainer="MariaDB Buildbot maintainers"

# Install updates and required packages
RUN zypper update -y && \
    zypper install -y -t pattern devel_basis && \
    zypper install -y \
    boost-devel \
    ccache \
    check-devel \
    cmake \
    cracklib-devel \
    curl \
    git \
    glibc-locale \
    gnutls-devel \
    jemalloc-devel \
    libboost_filesystem1_66_0-devel \
    libboost_program_options1_66_0-devel \
    libboost_system1_66_0-devel \
    libcurl-devel \
    libffi-devel \
    liblz4-devel \
    libxml2-devel \
    openssl-devel \
    policycoreutils \
    python-devel \
    python-pip \
    python3-pip \
    rpm-build \
    rpmlint \
    scons \
    snappy-devel \
    subversion \
    wget \
    && zypper -n si -d mariadb \
    && zypper clean -a \
    && curl -sLo /usr/local/bin/dumb-init "https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_$(uname -m)" \
    && chmod +x /usr/local/bin/dumb-init
