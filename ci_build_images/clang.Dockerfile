# this is to create images with Clang compiler for BB workers
RUN . /etc/os-release \
    && case "$VERSION" in \
        18.04*) \
          apt-get -y install --no-install-recommends clang-10; \
          ;; \
        *) \
          apt-get -y install --no-install-recommends clang-11; \
          ;; \
    esac \
    && apt-get clean
