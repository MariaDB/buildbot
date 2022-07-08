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
    && source "$HOME/.cargo/env" \
    && pip3 install --no-cache-dir -U pip \
    && curl -so /root/requirements.txt \
       https://raw.githubusercontent.com/MariaDB/buildbot/main/ci_build_images/requirements.txt \
    && pip3 install --no-cache-dir --no-warn-script-location -r /root/requirements.txt
