# Buildbot worker for building MariaDB
#
# Provides a base RHEL-7 AMD64 image with latest buildbot worker installed
# and MariaDB build dependencies

ARG BASE_IMAGE
FROM registry.access.redhat.com/$BASE_IMAGE AS repo

LABEL maintainer="MariaDB Buildbot maintainers"

RUN --mount=type=secret,id=rhel_orgid,target=/run/secrets/rhel_orgid \
    --mount=type=secret,id=rhel_keyname,target=/run/secrets/rhel_keyname \
    # Make subscription-manager work in container
    sed -i 's/\(def in_container():\)/\1\n    return False/g' /usr/lib64/python*/*-packages/rhsm/config.py \
    && subscription-manager register \
         --org="$(cat /run/secrets/rhel_orgid)" \
         --activationkey="$(cat /run/secrets/rhel_keyname)" \
    && subscription-manager repos --enable=rhel-7-server-optional-rpms \
    && rpm -ivh https://dl.fedoraproject.org/pub/archive/epel/7/x86_64/Packages/e/epel-release-7-14.noarch.rpm \
    #TODO(razvanv): Currently Galera 26.4.20-1.el7_9. Run RH 7 Galera builder and rebuild this image to update latest-galera
    && yum-config-manager --add-repo https://ci.mariadb.org/galera/mariadb-4.x-latest-gal-amd64-rhel-7.repo

FROM repo AS buildeps
# hadolint ignore=DL3032
RUN yum -y upgrade \
     && yum-builddep -y mariadb-server \
     && yum -y install \
          @development \
          asio-devel \
          bison \
          boost-devel \
          bzip2 \
          bzip2-devel \
          ccache \
          check-devel \
          cmake3 \
          cracklib-devel \
          createrepo \
          curl-devel \
          fmt-devel \
          galera-4 \
          gnutls-devel \
          java-1.8.0-openjdk \
          java-1.8.0-openjdk-devel \
          jemalloc-devel \
          libaio-devel \
          libevent-devel \
          libffi-devel \
          libpmem-devel \
          libzstd-devel \
          libxml2-devel \
          lsof \
          lz4-devel \
          lzo-devel \
          openssl-devel \
          ncurses-devel \
          pam-devel \
          perl-autodie \
          perl-devel \
          perl-Net-SSLeay \
          pcre2-devel \
          python3-devel \
          python3-pip \
          readline-devel \
          rpmlint \
          ruby \
          snappy-devel \
          socat \
          systemd-devel \
          unixODBC \
          unixODBC-devel \
          wget \
     && yum -y install \
          "https://kojipkgs.fedoraproject.org/packages/Judy/1.0.5/7.el7/x86_64/Judy-1.0.5-7.el7.x86_64.rpm" \
          "https://kojipkgs.fedoraproject.org/packages/Judy/1.0.5/7.el7/x86_64/Judy-devel-1.0.5-7.el7.x86_64.rpm" \
     # USE CMAKE 3
     && yum -y remove cmake \
     && ln -sf /usr/bin/cmake3 /usr/bin/cmake \
     && curl -sL "https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_$(uname -m)" >/usr/local/bin/dumb-init \
     && chmod +x /usr/local/bin/dumb-init

ENV CRYPTOGRAPHY_ALLOW_OPENSSL_102=1
ENV WSREP_PROVIDER=/usr/lib64/galera/libgalera_smm.so


FROM buildeps AS cleanup
RUN yum clean all \
     && subscription-manager unregister

# FRAGMENT DOCKERFILES (bb-worker, pip, etc) ARE CONCATENATED HERE
FROM cleanup as fragments
