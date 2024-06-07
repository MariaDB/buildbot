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

USER buildbot

WORKDIR /home/buildbot

# Clone the jepsen-mysql repository, download leiningen, and set permissions
RUN git clone https://github.com/vlad-lesin/jepsen-mysql \
    && curl -o ~/lein https://raw.githubusercontent.com/technomancy/leiningen/stable/bin/lein \
    && chmod a+x ~/lein

WORKDIR /home/buildbot/jepsen-mysql

# Create necessary directories and run leiningen to download dependencies
RUN mkdir -p /home/buildbot/mariadb-bin/tmp \
    &&  ~/lein run test --help

WORKDIR /home/buildbot