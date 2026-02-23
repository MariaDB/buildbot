from configuration.builders.base import GenericBuilder
from configuration.builders.sequences.connectors.conodbc import deb, rpm, tarball

TARBALL = GenericBuilder(name="codbc-tarball-docker", sequences=[tarball()])


AMD64_RPM_BUILDERS = [
    GenericBuilder(name="codbc-amd64-fedora43", sequences=[rpm()]),
    GenericBuilder(name="codbc-amd64-fedora42", sequences=[rpm()]),
]

AMD64_DEB_BUILDERS = [
    GenericBuilder(name="codbc-amd64-debian12", sequences=[deb()]),
    GenericBuilder(name="codbc-amd64-debian11", sequences=[deb()]),
]
RPM_BUILDERS = [*AMD64_RPM_BUILDERS]

DEB_BUILDERS = [*AMD64_DEB_BUILDERS]
