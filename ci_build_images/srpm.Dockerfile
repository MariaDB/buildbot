# Standalone Dockerfile (can be built alone) for providing minimal container images to re-build the server from a source RPM
    # for every OS << BASE_IMAGE >> enable required repositories and install the RPM toolset
    # buildbot user configuration

ARG BASE_IMAGE
FROM "$BASE_IMAGE"
ARG BASE_IMAGE
LABEL maintainer="MariaDB Buildbot maintainers"

# REPOSITORY AND RPM TOOLS SETUP
# hadolint ignore=SC2086
RUN source /etc/os-release \
    && case $PLATFORM_ID in  \
        "platform:el8"|"platform:el9"|"platform:el10"|"platform:f41"|"platform:f42") \
            dnf -y upgrade \
            && dnf -y install rpm-build yum-utils wget which perl-generators sudo gcc-c++; \
            case $ID in \
                "rhel") \
                    rpm -ivh https://dl.fedoraproject.org/pub/epel/epel-release-latest-${PLATFORM_ID##*:el}.noarch.rpm; \
                    # crb in rhel is enabled with a valid subscription, will be handled by running the container in an RH host
                    ;; \
                "centos") \
                    dnf -y install epel-release \
                    && dnf config-manager --set-enabled crb; \
                    ;; \
            esac; \
            dnf install -y ccache \
            && dnf clean all; \
            ;; \
        *) \
            # No $PLATFORM_ID in SUSE nor RH7
            case $BASE_IMAGE in \
                *leap:15.6|*bci-base:15.6) \
                    zypper -n update \
                    && zypper -n install rpm-build wget which sudo gcc-c++ ccache \
                    && zypper clean; \
                ;; \
                # Only AMD64 until EOL
                *ubi7) \
                    yum -y upgrade \
                    && rpm -ivh https://dl.fedoraproject.org/pub/archive/epel/7/x86_64/Packages/e/epel-release-7-14.noarch.rpm \
                    && yum -y install rpm-build \
                        yum-utils \
                        wget \
                        which \
                        perl-generators \
                        sudo \
                        gcc-c++ \
                        ccache \
                    && yum clean all; \
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


RUN ln -s /home/buildbot /buildbot
WORKDIR /buildbot
USER buildbot
