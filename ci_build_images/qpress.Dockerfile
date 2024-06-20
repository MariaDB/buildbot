
# qpress.Dockerfile
# those steps are common to all images
USER root

# install qpress (MDEV-29043)
COPY qpress/* /tmp/qpress/
WORKDIR /tmp/qpress
RUN make -j"$(nproc)" \
    && cp qpress /usr/local/bin/ \
    && rm -rf /tmp/qpress
