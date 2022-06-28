# Buildbot master container
# todo:
#   - use multiple containers to build (save space)
#   - create bbm and bbm-web containers on quay.io

FROM debian:11 AS builder
LABEL maintainer="MariaDB Buildbot maintainers"
ARG DEBIAN_FRONTEND=noninteractive

# Install required packages
WORKDIR /root
RUN apt-get update \
    && apt-get -y install --no-install-recommends \
      build-essential \
      git \
      libmariadb-dev \
      libvirt-dev \
      nodejs \
      npm \
      python3-dev \
      python3-pip \
      python3-venv \
      pkg-config \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --location=global yarn \
    && export PATH="$HOME/node_modules/.bin:$PATH" \
    && yarn global add gulp yo generator-buildbot-dashboard

# Install buildbot fork (master-web)
WORKDIR /opt
RUN git clone --branch grid https://github.com/vladbogo/buildbot buildbot \
    && python3 -m venv buildbot/.venv \
    && . buildbot/.venv/bin/activate \
    && pip install --no-cache-dir pip -U \
    && pip install --no-cache-dir \
      buildbot-prometheus \
      buildbot-worker \
      docker \
      flask \
      libvirt-python \
      mock \
      mysqlclient \
      pyzabbix \
      treq \
      wheel \
    && pip install --no-cache-dir sqlalchemy==1.3.23

WORKDIR /opt/buildbot/master
RUN . /opt/buildbot/.venv/bin/activate \
    && python setup.py bdist_wheel \
    && pip install --no-cache-dir dist/*.whl

# actual image, see https://docs.docker.com/develop/develop-images/multistage-build/
FROM debian:11-slim
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get -y install --no-install-recommends \
      libmariadb-dev \
      python3 \
      python3-distutils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/buildbot /opt/buildbot
RUN ln -s /opt/buildbot/.venv/bin/buildbot /usr/local/bin/buildbot
