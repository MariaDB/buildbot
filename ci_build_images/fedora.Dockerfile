# Buildbot worker for building MariaDB
#
# Provides a base Fedora image with latest buildbot worker installed
# and MariaDB build dependencies

ARG base_image
FROM "$base_image"
LABEL maintainer="MariaDB Buildbot maintainers"

# Install updates and required packages
RUN dnf -y upgrade \
    && dnf -y install 'dnf-command(builddep)' \
    && dnf -y builddep mariadb-server \
    && dnf -y install \
    @development-tools \
    buildbot-worker \
    bzip2 \
    bzip2-devel \
    bzip2-libs \
    ccache \
    check-devel \
    createrepo \
    curl-devel \
    dumb-init \
    flex \
    fmt-devel \
    galera \
    gawk \
    iproute \
    java-1.8.0-openjdk-devel \
    java-1.8.0-openjdk \
    jemalloc-devel \
    libcurl-devel \
    libevent-devel \
    libffi-devel \
    liburing-devel \
    libdbi \
    lsof \
    lzo \
    lzo-devel \
    perl-autodie \
    python-unversioned-command \
    python3-devel \
    readline-devel \
    rpm-build \
    rpmlint \
    rsync \
    rubypick \
    scons \
    snappy-devel \
    socat \
    unixODBC \
    unixODBC-devel \
    wget \
    which \
    && source /etc/os-release \
    && if [ "$(uname -m)" = "x86_64" ]; then dnf -y install libpmem-devel; fi \
    && dnf clean all

ENV WSREP_PROVIDER=/usr/lib64/galera/libgalera_smm.so
