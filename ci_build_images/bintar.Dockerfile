# Buildbot worker for building MariaDB
#
# Provides a bintar image based on AlmaLinux with build dependencies
# and statically compiled libraries

# hadolint global ignore=DL3059
ARG BASE_IMAGE
FROM "$BASE_IMAGE" AS buildeps
LABEL maintainer="MariaDB Buildbot maintainers"

# Install updates and required packages
# hadolint ignore=SC2086
RUN dnf -y install 'dnf-command(config-manager)' \
    && source /etc/os-release \
    && ARCH=amd64 \
    && dnf -y --enablerepo=extras install epel-release \
    && dnf config-manager --set-enabled powertools \
    && dnf -y module enable mariadb-devel \
    && dnf -y install almalinux-release-devel \
    && VERSION_ID=-${VERSION_ID} \
    && VERSION_ID=${VERSION_ID%%.*} \
    && dnf config-manager --add-repo https://ci.mariadb.org/galera/mariadb-4.x-latest-gal-${ARCH}-rhel${VERSION_ID}.repo \
    && dnf -y upgrade \
    && dnf -y groupinstall "Development Tools" \
    && dnf -y builddep mariadb-server \
    && dnf -y install \
    asio-devel \
    buildbot-worker \
    bzip2 \
    bzip2-devel \
    ccache \
    check-devel \
    cracklib-devel \
    createrepo \
    curl-devel \
    eigen3-devel \
    flex \
    galera-4 \
    java-1.8.0-openjdk-devel \
    java-1.8.0-openjdk \
    jemalloc-devel \
    libcurl-devel \
    libevent-devel \
    libffi-devel \
    libpmem-devel \
    libxml2-devel \
    libzstd-devel \
    lzo-devel \
    perl-autodie \
    perl-Net-SSLeay \
    python3-devel \
    readline-devel \
    rpmlint \
    ruby \
    snappy-devel \
    subversion \
    unixODBC \
    unixODBC-devel \
    wget \
    which \
    xz-devel \
    yum-utils \
    && dnf clean all \
    && curl -sL "https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_$(uname -m)" >/usr/local/bin/dumb-init \
    && chmod +x /usr/local/bin/dumb-init
ENV WSREP_PROVIDER=/usr/lib64/galera-4/libgalera_smm.so

## Build the static libraries in a separate stage so we save space
FROM buildeps AS staticlibs

COPY ci_build_images/scripts/* /scripts/
WORKDIR /scripts
RUN chmod +x ./*.sh && ls -l

# Build static libraries
RUN mkdir -p ./local/lib/
RUN ./libaio.sh
RUN ./liblz4.sh
RUN ./xz.sh
RUN ./ncurses.sh
RUN ./libpmem.sh
RUN ./libzstd.sh
RUN ./gnutls.sh

FROM buildeps AS bintar
COPY --from=staticlibs /scripts/local/lib /scripts/local/lib
COPY --from=staticlibs /root/gnutlsa.tar.bz2 /scripts/

WORKDIR /scripts
RUN tar -xvf gnutlsa.tar.bz2 -C / && ldconfig


### Other .Dockerfiles will be concatenated here (worker, qpress, etc)