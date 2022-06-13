RUN wget ci.mariadb.org/helper_files/aocc-compiler-amd64.deb

RUN dpkg -i aocc-compiler*.deb
RUN apt-get -y install clang

RUN gosu buildbot cat /opt/AMD/aocc-compiler-*/setenv_AOCC.sh >> ~/.bashrc
