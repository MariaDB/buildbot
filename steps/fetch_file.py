from buildbot.plugins import util
from .base import Command


class FetchTarball(Command):
    def __init__(self, url: str, workdir: str):
        super().__init__(name='Fetch Source Tarball',
                         workdir=workdir)
        self.name = 'Fetch Source Tarball'
        self.url = url

    def as_cmd_arg(self) -> list[str]:
        return [
            'wget',
            util.Interpolate(f'{self.url}/%(prop:tarbuildnum)s'),
        ]
