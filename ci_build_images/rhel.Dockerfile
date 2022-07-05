# Builbot worker for building MariaDB
#
# Provides a base RHEL-8/9 image with latest buildbot worker installed
# and MariaDB build dependencies

ARG base_image
FROM registry.access.redhat.com/$base_image
ARG base_image
LABEL maintainer="MariaDB Buildbot maintainers"

# Install updates and required packages
# see: https://access.redhat.com/discussions/5889431 for rhsm/config.py hack.
# hadolint ignore=SC2034,DL3041,SC2086
RUN --mount=type=secret,id=rhel_orgid,target=/run/secrets/rhel_orgid \
    --mount=type=secret,id=rhel_keyname,target=/run/secrets/rhel_keyname \
    sed -i 's/\(def in_container():\)/\1\n    return False/g' /usr/lib64/python*/*-packages/rhsm/config.py \
    && subscription-manager register \
         --org="$(cat /run/secrets/rhel_orgid)" \
         --activationkey="$(cat /run/secrets/rhel_keyname)" \
    && case $base_image in \
    ubi9) \
      v=9; \
      # no buildbot-worker any more \
      extra="fmt-devel python3-pip"; \
      if [ "$(arch)" == "x86_64" ] || [ "$(arch)" == "ppc64le" ]; then \
         extra="$extra libpmem-devel"; \
      fi \
      ;; \
    ubi8) \
      v=8; \
      # fmt-devel # >= 7.0 needed, epel8 has 6.2.1-1.el8 \
      extra="buildbot-worker"; \
      if [ "$(arch)" == "x86_64" ]; then \
         extra="$extra libpmem-devel"; \
      fi \
      ;; \
    esac \
    && subscription-manager repos --enable "codeready-builder-for-rhel-${v}-$(uname -m)-rpms" \
    && rpm -ivh https://dl.fedoraproject.org/pub/epel/epel-release-latest-"${v}".noarch.rpm \
    && dnf -y upgrade \
    && dnf -y groupinstall "Development Tools" \
    && dnf -y install \
    "https://kojipkgs.fedoraproject.org/packages/Judy/1.0.5/28.fc36/$(arch)/Judy-1.0.5-28.fc36.$(arch).rpm" \
    "https://kojipkgs.fedoraproject.org/packages/Judy/1.0.5/28.fc36/$(arch)/Judy-devel-1.0.5-28.fc36.$(arch).rpm" \
    && dnf -y builddep mariadb-server \
    && dnf -y install \
    ${extra} \
    boost-devel \
    ccache \
    check-devel \
    checkpolicy \
    coreutils \
    cracklib-devel \
    createrepo \
    curl-devel \
    galera \
    java-1.8.0-openjdk \
    jemalloc-devel --allowerasing \
    krb5-devel \
    libaio-devel \
    libcurl-devel \
    libevent-devel \
    libffi-devel \
    liburing-devel \
    libxml2-devel \
    libzstd-devel \
    lz4-devel \
    ncurses-devel \
    openssl-devel \
    pam-devel \
    pcre2-devel \
    pkgconfig \
    policycoreutils \
    python3 \
    python3-devel \
    python3-scons \
    readline-devel \
    rpmlint \
    ruby \
    snappy-devel \
    subversion \
    systemd-devel \
    systemtap-sdt-devel \
    unixODBC \
    unixODBC-devel \
    wget \
    xz-devel \
    yum-utils \
    && dnf clean all \
    && subscription-manager unregister \
    # dumb-init rpm is not available on rhel \
    && curl -sL "https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_$(uname -m)" >/usr/local/bin/dumb-init \
    && chmod +x /usr/local/bin/dumb-init

ENV WSREP_PROVIDER=/usr/lib64/galera/libgalera_smm.so
