# Create the buildbot user - this step is common to all Dockerfiles
# but needs to run before custom code

# Create buildbot user
RUN useradd -ms /bin/bash buildbot \
    && gosu buildbot curl -so /home/buildbot/buildbot.tac \
    # TODO move buildbot.tac to ci_build_images
    https://raw.githubusercontent.com/MariaDB/buildbot/main/dockerfiles/buildbot.tac \
    && echo "[[ -d /home/buildbot/.local/bin/ ]] && export PATH=\"/home/buildbot/.local/bin:\$PATH\"" >>/home/buildbot/.bashrc \
    # autobake-deb (debian/ubuntu) will need sudo rights \
    && if grep -qi "debian" /etc/os-release; then \
        usermod -a -G sudo buildbot; \
        echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers; \
    fi


