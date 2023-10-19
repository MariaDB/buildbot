# Buildbot master and master-web containers

FROM debian:11-slim
LABEL maintainer="MariaDB Buildbot maintainers"
ARG DEBIAN_FRONTEND=noninteractive
ARG master_type="master"

WORKDIR /opt/buildbot
# hadolint ignore=DL3003
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get -y install --no-install-recommends \
      build-essential \
      git \
      libmariadb-dev \
      libvirt-dev \
      netcat \
      openssh-client \
      pkg-config \
      python3 \
      python3-dev \
      python3-distutils \
      python3-pip \
      python3-venv \
    && if [ "$master_type" = "master-web" ]; then \
      apt-get -y install --no-install-recommends \
        libcairo2 \
        yarnpkg; \
      export PATH="/usr/share/nodejs/yarn/bin:$PATH"; \
      yarn global --ignore-engines add gulp yo generator-buildbot-dashboard; \
    fi \
    && git clone --branch grid https://github.com/vladbogo/buildbot . \
    && python3 -m venv .venv \
    && . .venv/bin/activate \
    && if [ "$master_type" = "master-web" ]; then \
      make frontend; \
    fi \
    && pip install --no-cache-dir python-dotenv wheel \
    && pip install --no-cache-dir autobahn==20.7.1 PyJWT==1.7.1 \
    && cd master && python setup.py bdist_wheel \
    && pip install --no-cache-dir dist/*.whl \
    && pip install --no-cache-dir pip -U \
    && pip install --no-cache-dir \
      buildbot-prometheus \
      buildbot-worker \
      docker==4.3.1 \
      flask \
      libvirt-python \
      mock \
      mysqlclient \
      pyzabbix \
      sqlalchemy==1.3.23 \
      treq \
      twisted==22.10.0 \
    && if [ "$master_type" = "master-web" ]; then \
      pip install --no-cache-dir pyjade; \
    fi \
    && ln -s /opt/buildbot/.venv/bin/buildbot /usr/local/bin/buildbot \
    # cleaning \
    && apt-get purge -y \
      build-essential \
      pkg-config \
      python3-dev \
      python3-pip \
      python3-venv \
    && if [ "$master_type" = "master-web" ]; then \
      apt-get purge -y yarnpkg; \
      rm -rf "$(find /opt/buildbot -maxdepth 3 -name node_modules)"; \
    fi \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
