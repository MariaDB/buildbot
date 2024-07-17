#
# Buildbot worker for building MariaDB
#
# Provides a base SLES image with latest buildbot worker installed
# and MariaDB build dependencies

ARG BASE_IMAGE
FROM "$BASE_IMAGE"
LABEL maintainer="MariaDB Buildbot maintainers"

COPY --chmod=755 mariadb_zypper_expect /
# Install updates and required packages
RUN zypper -n update \
    && zypper -n install -t pattern devel_basis \
    && zypper -n install \
    bzip2 \
    ccache \
    check-devel \
    checkpolicy \
    cmake \
    cracklib-devel \
    createrepo_c \
    expect \
    gcc-c++ \
    gdb \
    git \
    glibc-locale \
    jemalloc-devel \
    libaio-devel \
    libboost_filesystem1_66_0-devel \
    libboost_program_options1_66_0-devel \
    libboost_system1_66_0-devel \
    libcurl-devel \
    libffi-devel \
    libfmt8 \
    libgnutls-devel \
    liblz4-devel \
    libopenssl-3-devel \
    liburing2-devel \
    perl-Net-SSLeay \
    policycoreutils \
    python312-devel \
    python312-pip \
    rpm-build \
    rpmlint \
    snappy-devel \
    subversion \
    wget \
    # temporary add opensuse oss repo for some deps \
    && zypper ar -f https://download.opensuse.org/distribution/leap/RELEASEVER/repo/oss/ repo-oss \
    && sed -i "s/RELEASEVER/\$releasever/" /etc/zypp/repos.d/repo-oss.repo \
    && zypper -n --no-gpg-checks install \
    judy-devel \
    && rm /etc/zypp/repos.d/repo-oss.repo \
    && zypper modifyrepo --enable SLE_BCI_source \
    && ./mariadb_zypper_expect \
    && zypper clean -a \
    && curl -sLo /usr/local/bin/dumb-init "https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_$(uname -m)" \
    && chmod +x /usr/local/bin/dumb-init
