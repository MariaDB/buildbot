# We install buildbot-worker from packages but for some OS it is not available
# and need to be installed via pip.

# Install a recent rust toolchain needed for some arch
# see: https://cryptography.io/en/latest/installation/
# then upgrade pip and install BB worker requirements
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs >/tmp/rustup-init.sh \
    # rust installer does not detect i386 arch \
    && case $(getconf LONG_BIT) in \
        "32") bash /tmp/rustup-init.sh -y --default-host=i686-unknown-linux-gnu --profile=minimal ;; \
        *) bash /tmp/rustup-init.sh -y --profile=minimal ;; \
    esac \
    && rm -f /tmp/rustup-init.sh \
    # for Centos7/ppcle64, specific pip packages versions \
    # and python3-devel are needed \
    && if grep -q "CentOS Linux release 7" /etc/centos-release || \
      grep -q "Red Hat Enterprise Linux Server release 7" /etc/redhat-release && \
      [ "$(arch)" = "ppc64le" ]; then \
        yum -y install python3-devel; \
        yum clean all; \
        pip3 install --no-cache-dir cffi==1.14.3 cryptography==3.1.1 pyOpenSSL==19.1.0 twisted[tls]==20.3.0 buildbot-worker==2.8.4; \
    else \
        pip3 install --no-cache-dir -U pip; \
        curl -so /root/requirements.txt \
        https://raw.githubusercontent.com/MariaDB/buildbot/main/ci_build_images/requirements.txt; \
        # https://jira.mariadb.org/browse/MDBF-329 \
        if grep -q "stretch" /etc/apt/sources.list; then \
           pip3 install --no-cache-dir --no-warn-script-location incremental; \
        fi; \
        pip3 install --no-cache-dir --no-warn-script-location -r /root/requirements.txt; \
    fi
