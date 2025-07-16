# Buildbot worker for building MariaDB
#
# Provides a base Fedora image with latest buildbot worker installed
# and MariaDB build dependencies

ARG BASE_IMAGE
FROM "$BASE_IMAGE"
LABEL maintainer="MariaDB Buildbot maintainers"
ARG INSTALL_VALGRIND

# Install updates and required packages
RUN echo "fastestmirror=true" >> /etc/dnf/dnf.conf \
    && dnf -y upgrade \
    && dnf -y install 'dnf-command(builddep)' 'dnf-command(config-manager)' \
    && . /etc/os-release \
    && ARCH=$(rpm --query --queryformat='%{ARCH}' rpm) \
    && if [ "$ARCH" = x86_64 ]; then ARCH=amd64 ; fi \
    && dnf config-manager --add-repo https://ci.mariadb.org/galera/mariadb-4.x-latest-gal-"${ARCH}"-fedora-"${VERSION_ID}".repo \
    && dnf -y builddep mariadb-server \
    && dnf -y install \
    @development-tools \
    asio-devel \
    buildbot-worker \
    bzip2 \
    bzip2-devel \
    bzip2-libs \
    ccache \
    check-devel \
    createrepo \
    curl-devel \
    dumb-init \
    eigen3-devel \
    flex \
    fmt-devel \
    galera-4 \
    gawk \
    gdb \
    iproute \
    jemalloc-devel \
    libaio-devel \
    libcurl-devel \
    libevent-devel \
    libffi-devel \
    liburing-devel \
    libdbi \
    lsof \
    lzo \
    lzo-devel \
    perl-autodie \
    perl-Net-SSLeay \
    python-unversioned-command \
    python3-devel \
    readline-devel \
    rpm-build \
    rpmlint \
    rsync \
    rubypick \
    snappy-devel \
    socat \
    unixODBC \
    unixODBC-devel \
    wget \
    which \
    && if [ "$VERSION_ID" = "42" ]; then \
        dnf -y install java-latest-openjdk-devel java-latest-openjdk; \
    else \
        dnf -y install java-1.8.0-openjdk-devel java-1.8.0-openjdk; \
    fi \
    && if [ "$(uname -m)" = "x86_64" ]; then dnf -y install libpmem-devel; fi \
    && if [ "$INSTALL_VALGRIND" = "true" ]; then dnf -y install valgrind; fi \
    && dnf clean all

ENV WSREP_PROVIDER=/usr/lib64/galera-4/libgalera_smm.so
