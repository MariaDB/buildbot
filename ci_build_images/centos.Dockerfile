# Buildbot worker for building MariaDB
#
# Provides a base CentOS image with latest buildbot worker installed
# and MariaDB build dependencies

ARG BASE_IMAGE
FROM "$BASE_IMAGE"
LABEL maintainer="MariaDB Buildbot maintainers"

# Install updates and required packages
# hadolint ignore=SC2086
RUN dnf -y install 'dnf-command(config-manager)' \
    && source /etc/os-release \
    && ARCH=$(rpm --query --queryformat='%{ARCH}' rpm) \
    && case "$PLATFORM_ID" in \
        "platform:el9") \
          # centosstream9/almalinux9/rockylinux9 \
          dnf -y install epel-release; \
          dnf config-manager --set-enabled crb; \
          extra="python3-pip"; \
          ;; \
        *) \
          dnf -y --enablerepo=extras install epel-release; \
          dnf config-manager --set-enabled powertools; \
          dnf -y module enable mariadb-devel; \
          extra="buildbot-worker"; \
          ;; \
    esac \
    && case "$ID" in \
        "centos") \
          ID=centos-stream; \
          ;; \
        "rocky") \
          ID=rockylinux; \
          ;& \
        "almalinux") \
          if [ "$ARCH" == "aarch64" ]; then ID=rhel; fi ; \
          ;; \
    esac \
    && VERSION_ID=${VERSION_ID%%.*} \
    && if [ $ARCH = x86_64 ]; then ARCH=amd64 ; fi \
    && dnf config-manager --add-repo https://ci.mariadb.org/galera/mariadb-4.x-latest-gal-${ARCH}-${ID}-${VERSION_ID}.repo \
    && dnf -y upgrade \
    && dnf -y groupinstall "Development Tools" \
    && dnf -y builddep mariadb-server \
    && dnf -y install \
    # not sure if needed \
    # perl \
    ${extra} \
    bzip2 \
    bzip2-devel \
    ccache \
    check-devel \
    cracklib-devel \
    createrepo \
    curl-devel \
    flex \
    galera-4 \
    java-1.8.0-openjdk-devel \
    java-1.8.0-openjdk \
    jemalloc-devel \
    libcurl-devel \
    libevent-devel \
    libffi-devel \
    libxml2-devel \
    libzstd-devel \
    perl-autodie \
    perl-Net-SSLeay \
    python3-devel \
    python3-scons \
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
    && if [ "$(uname -m)" = "x86_64" ]; then dnf -y install libpmem-devel; fi \
    && dnf clean all \
    # dumb-init rpm is not available on centos (official repo) \
    && curl -sL "https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_$(uname -m)" >/usr/local/bin/dumb-init \
    && chmod +x /usr/local/bin/dumb-init

ENV WSREP_PROVIDER=/usr/lib64/galera/libgalera_smm.so
