# this is to create images with Clang compiler for BB workers
RUN . /etc/os-release \
    && case "$VERSION" in \
        18.04*) \
          apt-get -y install --no-install-recommends clang-10; \
          ;; \
        20.04*) \
          apt-get -y install --no-install-recommends clang-11; \
          ;; \
        *) \
          curl -sL https://apt.llvm.org/llvm-snapshot.gpg.key | \
            gpg --dearmor -o /usr/share/keyrings/llvm-snapshot.gpg \
          && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/llvm-snapshot.gpg] \
            http://apt.llvm.org/jammy/ llvm-toolchain-jammy-15 main" > /etc/apt/sources.list.d/llvm-toolchain.list \
          && apt-get update \
          && apt-get -y install --no-install-recommends clang-15; \
          ;; \
    esac \
    && apt-get clean
