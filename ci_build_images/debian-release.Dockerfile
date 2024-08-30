# Buildbot worker for building MariaDB
#
# Provides a base Debian image with latest buildbot worker installed for prep
# release works.

ARG BASE_IMAGE
FROM "$BASE_IMAGE"
LABEL maintainer="MariaDB Buildbot maintainers"

# This will make apt-get install without question
ARG DEBIAN_FRONTEND=noninteractive

# Install updates and required packages
RUN . /etc/os-release; \
    apt-get update \
    && apt-get -y upgrade \
    && apt-get -y install --no-install-recommends \
    aptly \
    ca-certificates \
    curl \
    dumb-init \
    gnupg2 \
    python3-buildbot-worker \
    rsync \
    sudo
