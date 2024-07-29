# Buildbot worker for building and running nodejs against MariaDB server
#
# Provides a base Ubuntu image with latest buildbot worker installed
# and nodejs build dependencies

FROM  node:17-buster-slim
LABEL maintainer="Anel Husakovic anel@mariadb.org"

ARG DEBIAN_FRONTEND=noninteractive

# Install updates and required packages
RUN apt-get update -y && \
    apt-get install -y   \
      curl               \
      gcc                \
      git                \
      python3-pip        \
      libsnappy1v5 libnuma1 libpmem1 \
      libaio1 libreadline5 libncurses6 liblzo2-2 libtinfo5 libncurses5 && \
   rm -rf /var/lib/apt/lists/*

# Create buildbot user
RUN useradd -ms /bin/bash buildbot && \
    mkdir -p /buildbot /data && \
    chown -R buildbot /buildbot /data /usr/local && \
    curl -o /buildbot/buildbot.tac https://raw.githubusercontent.com/MariaDB/buildbot/main/dockerfiles/buildbot.tac

WORKDIR /buildbot

# Upgrade pip and install packages
RUN pip3 install -U pip virtualenv
RUN pip3 install buildbot-worker && \
    pip3 --no-cache-dir install 'twisted[tls]'

# Test runs produce a great quantity of dead grandchild processes.  In a
# non-docker environment, these are automatically reaped by init (process 1),
# so we need to simulate that here.  See https://github.com/Yelp/dumb-init
RUN curl https://github.com/Yelp/dumb-init/releases/download/v1.2.2/dumb-init_1.2.2_$(dpkg --print-architecture).deb -Lo /tmp/init.deb && dpkg -i /tmp/init.deb

CMD ["/usr/bin/dumb-init", "twistd", "--pidfile=", "-ny", "buildbot.tac"]

