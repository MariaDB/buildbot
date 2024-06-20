USER root

# Install additional packages
RUN apt-get update && apt-get -y install --no-install-recommends \
    apt-transport-https \
    automake \
    bison \
    dpkg-dev \
    dirmngr \
    faketime \
    gnuplot \
    graphviz \
    libaio-dev \
    libncurses-dev \
    libpcre2-dev \
    libtool \
    libzip4 \
    logrotate \
    make \
    man-db \
    netcat-openbsd \
    ntpdate \
    openjdk-21-jdk \
    openjdk-21-jre \
    openssh-client \
    openssh-server \
    pkg-config \
    rsyslog \
    tcpdump \
    unzip \
    curl \
    && apt-get clean

RUN if [ ! -d /home/buildbot ]; then mkdir /home/buildbot; fi \
    && chown -R buildbot:buildbot /home/buildbot

USER buildbot

WORKDIR /home/buildbot

# Clone the jepsen-mysql repository, download leiningen, and set permissions
RUN git clone https://github.com/vlad-lesin/jepsen-mysql jepsen-mariadb \
    && curl -o /home/buildbot/lein https://raw.githubusercontent.com/technomancy/leiningen/stable/bin/lein \
    && chmod a+x /home/buildbot/lein

WORKDIR /home/buildbot/jepsen-mariadb

# Create necessary directories and run leiningen to download dependencies
RUN mkdir -p /home/buildbot/mariadb-bin/tmp \
    &&  /home/buildbot/lein run test --help

WORKDIR /home/buildbot
