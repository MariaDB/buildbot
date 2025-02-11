# INSTALL MINIO
# All configured values are defaults for MTR
# USAGE: minio server /tmp/minio > /dev/null 2>&1 &


# Creating /tmp/minio/storage-engine is a pretty way of defining a bucket
# Just remember to start the server with << minio server /tmp/minio/ >>
RUN curl -sSL https://dl.min.io/server/minio/release/linux-amd64/minio -o minio \
    && chmod +x minio \
    && mv minio /usr/local/bin \
    && mkdir -p /tmp/minio/storage-engine && chown -R 1000:root /tmp/minio

# Address is required so that MiniO won't bind to Docker bridge,
# exposing itself to outer world (host)
ENV MINIO_ROOT_USER=minio
ENV MINIO_ROOT_PASSWORD=minioadmin
ENV MINIO_ADDRESS=127.0.0.1:9000
ENV MINIO_CONSOLE_ADDRESS=127.0.0.1:9001