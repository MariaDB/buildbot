# Buildbot worker for building MariaDB
#
# Provides a base Fedora image with latest buildbot worker installed
# and MariaDB build dependencies

ARG BASE_IMAGE
FROM "$BASE_IMAGE"
LABEL maintainer="MariaDB Buildbot maintainers"

# Install updates and required packages
RUN echo "fastestmirror=true" >> /etc/dnf/dnf.conf \
    && dnf -y upgrade \
    && dnf -y install 'dnf-command(builddep)' 'dnf-command(config-manager)' \
    && source /etc/os-release \
    && ARCH=$(rpm --query --queryformat='%{ARCH}' rpm) \
    && if [ "$ARCH" = x86_64 ]; then ARCH=amd64 ; fi \
    && dnf config-manager --add-repo https://ci.mariadb.org/galera/mariadb-4.x-latest-gal-"${ARCH}"-fedora-"${VERSION_ID}".repo \
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
    galera-4 \
    gawk \
    gdb \
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
    perl-Net-SSLeay \
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
    && if [ "$VERSION_ID" = 39 ]; then curl -s 'https://gitlab.kitware.com/cmake/cmake/-/raw/v3.28.5/Modules/Internal/CPack/CPackRPM.cmake?ref_type=tags' -o /usr/share/cmake/Modules/Internal/CPack/CPackRPM.cmake ; fi \
    && if [ "$(uname -m)" = "x86_64" ]; then dnf -y install libpmem-devel; fi \
    && dnf clean all

ENV WSREP_PROVIDER=/usr/lib64/galera/libgalera_smm.so
