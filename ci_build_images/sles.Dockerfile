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
    && . /etc/os-release \
    && if [ "$VERSION_ID" = "15.7" ]; then \
         BOOST_VER=1_66_0; \
         FMT_VER=8; \
         LIBURING_VER=2; \
       else \
         BOOST_VER=1_86_0; \
         FMT_VER=11; \
         LIBURING_VER=; \
       fi \
    && VERSION_ID="${VERSION_ID%%.*}0${VERSION_ID#*.}" \
    && ARCH=$(rpm --query --queryformat='%{ARCH}' zypper) \
    && if [ "$ARCH" = x86_64 ]; then ARCH=amd64 ; fi \
    && zypper addrepo https://ci.mariadb.org/galera/mariadb-4.x-latest-gal-"${ARCH}-${ID%%leap}-${VERSION_ID}".repo \
    && zypper -n install \
    bzip2 \
    ccache \
    check-devel \
    checkpolicy \
    cmake \
    cracklib-devel \
    createrepo_c \
    expect \
    galera-4 \
    gcc-c++ \
    gdb \
    git \
    glibc-locale \
    libaio-devel \
    libboost_atomic"${BOOST_VER}"-devel \
    libboost_chrono"${BOOST_VER}"-devel \
    libboost_date_time"${BOOST_VER}"-devel \
    libboost_filesystem"${BOOST_VER}"-devel \
    libboost_program_options"${BOOST_VER}"-devel \
    libboost_regex"${BOOST_VER}"-devel \
    libboost_system"${BOOST_VER}"-devel \
    libboost_thread"${BOOST_VER}"-devel \
    libcurl-devel \
    libffi-devel \
    libfmt"${FMT_VER}" \
    libgnutls-devel \
    liblz4-devel \
    libopenssl-3-devel \
    liburing"${LIBURING_VER}"-devel \
    libxml2-devel \
    pam-devel \
    pcre2-devel \
    perl-Net-SSLeay \
    policycoreutils \
    python313-devel \
    python313-pip \
    rpm-build \
    snappy-devel \
    systemd-devel \
    wget \
    # Using OSS repository only for judy-devel as a build-time dependency.
    # As of now libJudy1 is still 1.0.5 in BCI for both 15.6 and 15.7.
    # On the next bump recheck if libJudy and judy-devel versions are the same.
    # Note that 15.7 is not available because OpenSuse jumped from 15.6 to 16.0
    && zypper addrepo https://download.opensuse.org/distribution/leap/15.6/repo/oss/ repo-oss \
    && zypper --gpg-auto-import-keys ref repo-oss \
    && zypper -n install \
    judy-devel \
    && rm /etc/zypp/repos.d/repo-oss.repo \
    && zypper modifyrepo --enable SLE_BCI_source \
    && ./mariadb_zypper_expect \
    && zypper clean -a \
    && curl -sLo /usr/local/bin/dumb-init "https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_$(uname -m)" \
    && chmod +x /usr/local/bin/dumb-init

ENV WSREP_PROVIDER=/usr/lib64/galera-4/libgalera_smm.so
