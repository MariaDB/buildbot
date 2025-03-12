# Standalone Dockerfile (can be built alone) for providing minimal container images to re-build the server from a source RPM
#
    # for every OS << BASE_IMAGE >> enable required repositories and install the RPM toolset
    # buildbot user configuration
    # buildbot-worker configuration. Either from pip or OS default repos (if exists)

ARG INSTALL_WORKER_FROM_PIP
ARG BASE_IMAGE
FROM "$BASE_IMAGE"
ARG BASE_IMAGE
ARG INSTALL_WORKER_FROM_PIP
LABEL maintainer="MariaDB Buildbot maintainers"

# REPOSITORY AND RPM TOOLS SETUP
# hadolint ignore=SC2086
RUN source /etc/os-release \
    && case $PLATFORM_ID in  \
        "platform:el8"|"platform:el9"|"platform:f39"|"platform:f40"|"platform:f41") \
            dnf -y upgrade && \
            dnf -y install rpm-build yum-utils wget which perl-generators sudo; \
            case $ID in \
                "rhel") \
                    rpm -ivh https://dl.fedoraproject.org/pub/epel/epel-release-latest-${PLATFORM_ID: -1}.noarch.rpm; \
                    # crb in rhel is enabled with a valid subscription, will be handled by running the container in an RH host
                    ;; \
                "centos") \
                    dnf -y install epel-release && \
                    dnf config-manager --set-enabled crb; \
                    ;; \
            esac; \
            if [ "$INSTALL_WORKER_FROM_PIP" = Y ]; then \
                dnf -y install python3-pip; \
            else \
                dnf -y install buildbot-worker; \
            fi \
            && dnf clean all; \
            ;; \
        *) \
            # No $PLATFORM_ID in SUSE
            case $BASE_IMAGE in \
                *leap:15.6|*bci-base:15.6) \
                    zypper -n update && \
                    zypper -n install rpm-build wget which sudo && \
                    if [ "$INSTALL_WORKER_FROM_PIP" = Y ]; then \
                        zypper -n install python311-pip; \
                    else \
                        zypper -n install buildbot-worker; \
                    fi \
                    && zypper clean; \
                ;; \
            *) \
                echo "Unsupported base image: $BASE_IMAGE"; \
                exit 1; \
            ;; \
            esac; \
        ;; \
    esac


# BUILDOT USER SETUP
RUN if getent passwd 1000; then \
        userdel --force --remove "$(getent passwd 1000 | cut -d: -f1)"; \
    fi \
    && if grep -q '^buildbot:' /etc/passwd; then \
      usermod -s /bin/bash buildbot; \
      usermod -d /home/buildbot buildbot; \
    else \
      useradd -ms /bin/bash buildbot; \
    fi \
    # UID 1000 is required for AutoFS (sharing produced packages)
    && usermod -u 1000 buildbot \
    && if [ ! -d /home/buildbot ]; then \
      mkdir /home/buildbot; \
      chown -R buildbot:buildbot /home/buildbot; \
    fi \
    # rpm build-deps require sudo
    # on some platforms there is a default that ALL should ask for password when executing sudo << ALL ALL=(ALL) ALL >>
    && sed -i '/^ALL/d' /etc/sudoers \
    && sed -i '/^Defaults[[:space:]]targetpw/d' /etc/sudoers \
    && echo 'buildbot ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers;

## BUILDBOT-WORKER SETUP
# Install worker from pip
RUN if [ "$INSTALL_WORKER_FROM_PIP" = "Y" ]; then \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs >/tmp/rustup-init.sh && \
    case $(getconf LONG_BIT) in \
        "32") bash /tmp/rustup-init.sh -y --default-host=i686-unknown-linux-gnu --profile=minimal ;; \
        *) bash /tmp/rustup-init.sh -y --profile=minimal ;; \
    esac && \
    rm -f /tmp/rustup-init.sh && \
    source "$HOME/.cargo/env" && \
    # Disable until opensuse/sles dont break: && pip3 install --no-cache-dir -U pip && \
    curl -so /root/requirements.txt \
       https://raw.githubusercontent.com/MariaDB/buildbot/main/ci_build_images/requirements.txt && \
    pip3 install --no-cache-dir -r /root/requirements.txt; \
    fi

# Get buildbot.tac and use the right twistd
# some distributions install twistd3 instead of twistd \
RUN if ! which twistd >/dev/null; then \
        if [ -x /usr/bin/twistd3 ]; then \
            ln -s /usr/bin/twistd3 /usr/bin/twistd; \
        else \
            echo "twistd command not found"; \
            exit 1; \
        fi \
    fi \
    && curl -so /home/buildbot/buildbot.tac \
        https://raw.githubusercontent.com/MariaDB/buildbot/main/ci_build_images/buildbot.tac \
    && chmod +r /home/buildbot/buildbot.tac

# install dumb-init to launch worker process as pid 1
RUN curl -sLo /usr/local/bin/dumb-init "https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_$(uname -m)" \
&& chmod +x /usr/local/bin/dumb-init;

RUN ln -s /home/buildbot /buildbot
WORKDIR /buildbot
USER buildbot
CMD ["dumb-init", "twistd", "--pidfile=", "-ny", "/home/buildbot/buildbot.tac"]
