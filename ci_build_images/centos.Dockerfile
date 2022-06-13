# Buildbot worker for building MariaDB
#
# Provides a base CentOS image with latest buildbot worker installed
# and MariaDB build dependencies

ARG base_image
FROM "$base_image"
LABEL maintainer="MariaDB Buildbot maintainers"

# Install updates and required packages
RUN dnf -y --enablerepo=extras install epel-release \
    && dnf -y install 'dnf-command(config-manager)' \
    && dnf config-manager --set-enabled powertools \
    && dnf -y module enable mariadb-devel \
    && dnf -y upgrade \
    && dnf -y groupinstall "Development Tools" \
    && dnf -y builddep mariadb-server \
    && dnf -y install \
    # not sure if needed
    # perl \
    buildbot-worker \
    ccache \
    check-devel \
    cracklib-devel \
    curl-devel \
    java-1.8.0-openjdk \
    java-1.8.0-openjdk-devel \
    libcurl-devel \
    libevent-devel \
    libffi-devel \
    libxml2-devel \
    libzstd-devel \
    python3-devel \
    python3-scons \
    readline-devel \
    ruby \
    snappy-devel \
    subversion \
    unixODBC \
    unixODBC-devel \
    wget \
    xz-devel \
    yum-utils \
    && dnf clean all \
    # dumb-init rpm is not available on centos (official repo)
    && curl -sL "https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_$(uname -m)" >/usr/local/bin/dumb-init \
    && chmod +x /usr/local/bin/dumb-init
