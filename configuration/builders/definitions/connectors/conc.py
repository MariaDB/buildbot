from configuration.builders.base import GenericBuilder
from configuration.builders.sequences.connectors.conc import deb, rpm, tarball

TARBALL = GenericBuilder(name="cc-tarball-docker", sequences=[tarball()])

AMD64_RPM_BUILDERS = [
    GenericBuilder(name="cc-amd64-fedora43", sequences=[rpm()]),
    GenericBuilder(name="cc-amd64-fedora42", sequences=[rpm()]),
]

AMD64_DEB_BUILDERS = [
    GenericBuilder(name="cc-amd64-debian12", sequences=[deb()]),
    GenericBuilder(name="cc-amd64-debian11", sequences=[deb()]),
]
RPM_BUILDERS = [*AMD64_RPM_BUILDERS]

DEB_BUILDERS = [*AMD64_DEB_BUILDERS]
