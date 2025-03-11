#TODO(Razvan): GitHub workflow to build and push the images to QUAY/GHCR
# Not urgent, when the scripts will be integrated with BuildBot
FROM python:3.12-slim-bookworm

ARG SCRIPT

WORKDIR /bintcheck
RUN apt-get update \
    && apt-get -y upgrade \
    #binutils required for readelf, libmagic for python-magic
    && apt-get install -y libmagic1 binutils dumb-init \
    && apt-get clean

COPY scripts/bintars/*.py /bintcheck/
COPY scripts/bintars/BUILD/requirements.txt /bintcheck
COPY runtime_config/bintar_deps/*.yaml /bintcheck/config/

RUN pip install --no-cache-dir -r requirements.txt

ENV SCRIPT=${SCRIPT}
# sh -c required for variable substitution
# use dumb-init to run as PID 1 in container
ENTRYPOINT ["dumb-init", "sh", "-c", "python -u ${SCRIPT} \"$@\"", "--"]
