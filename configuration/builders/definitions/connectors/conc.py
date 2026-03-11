from configuration.builders.base import GenericBuilder
from configuration.builders.sequences.connectors.conc import deb, rpm, tarball

TARBALL = GenericBuilder(name="cc-tarball-docker", sequences=[tarball()])
RELEASE_BUILDERS_BY_ARCH = {"amd64": [], "aarch64": []}
