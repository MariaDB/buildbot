
# aocc.Dockerfile
# this is to create images with AMD compiler for BB workers
RUN curl -sL "https://ci.mariadb.org/helper_files/aocc-compiler-amd64.deb" >/tmp/aocc-compiler-amd64.deb \
    && dpkg -i /tmp/aocc-compiler-amd64.deb \
    && rm -f /tmp/aocc-compiler-amd64.deb \
    && cat /opt/AMD/aocc-compiler-*/setenv_AOCC.sh >>/etc/bash.bashrc \
    && apt-get -y install --no-install-recommends clang \
    && apt-get clean
