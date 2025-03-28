# Buildbot worker for building MariaDB
#
# Provides a base Debian image with latest buildbot worker installed for prep
# release works.

ARG BASE_IMAGE
FROM "$BASE_IMAGE"
LABEL maintainer="MariaDB Buildbot maintainers"

# Install updates and required packages
RUN . /etc/os-release; \
    apt-get update \
    && apt-get -y upgrade \
    && DEBIAN_FRONTEND=noninteractive apt-get -y install --no-install-recommends \
    aptly \
    buildbot-worker \
    ca-certificates \
    curl \
    dumb-init \
    gnupg2 \
    rsync \
    sudo
