
# common.Dockerfile
# those steps are common to all images

# install qpress (MDEV-29043)
COPY qpress/* /tmp/qpress/
WORKDIR /tmp/qpress
RUN make -j"$(nproc)" \
    && cp qpress /usr/local/bin/ \
    && rm -rf /tmp/qpress

# Configure buildbot user
RUN if getent passwd 1000; then \
        userdel --force --remove "$(getent passwd 1000 | cut -d: -f1)"; \
    fi \
    && if grep -q '^buildbot:' /etc/passwd; then \
      usermod -s /bin/bash buildbot; \
      usermod -d /home/buildbot buildbot; \
    else \
      useradd -ms /bin/bash buildbot; \
    fi \
    # make sure that buildbot user UID is fixed \
    && usermod -u 1000 buildbot \
    && if [ ! -d /home/buildbot ]; then \
      mkdir /home/buildbot; \
      chown -R buildbot:buildbot /home/buildbot; \
    fi \
    && curl -so /home/buildbot/buildbot.tac \
    https://raw.githubusercontent.com/MariaDB/buildbot/main/ci_build_images/buildbot.tac \
    && chmod +r /home/buildbot/buildbot.tac \
    # autobake-deb (debian/ubuntu) will need sudo rights \
    && if grep -qi "debian" /etc/os-release; then \
        usermod -a -G sudo buildbot; \
        echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers; \
    fi \
    # some distribution install twistd3 instead of twistd \
    && if ! which twistd >/dev/null; then \
      if [ -x /usr/bin/twistd3 ]; then \
        ln -s /usr/bin/twistd3 /usr/bin/twistd; \
      else \
        echo "twistd command not found"; \
        exit 1; \
      fi \
    fi

RUN ln -s /home/buildbot /buildbot
WORKDIR /buildbot
USER buildbot
CMD ["dumb-init", "twistd", "--pidfile=", "-ny", "/home/buildbot/buildbot.tac"]
