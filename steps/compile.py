from buildbot.plugins import util

from .base import Command


class CompileMakeCommand(Command):
    def __init__(self, verbose: bool, include_package: bool, workdir: str = ''):
        self.include_package = include_package
        self.verbose = verbose
        name = 'Compile - package' if self.include_package else 'Compile'
        super().__init__(name=name, workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        result = [
            'make',
            f'VERBOSE={1 if self.verbose else 0}',
            util.Interpolate('-j%s', util.Property('jobs', default='33')),
        ]
        if self.include_package:
            result.append('package')
        return result


class CompileCMakeCommand(Command):
    def __init__(self, verbose: bool, workdir: str = ''):
        self.verbose = verbose
        super().__init__(name='Compile', workdir=workdir)

    def as_cmd_arg(self) -> list[str]:
        return [
            'cmake',
            '--build'
            '--verbose' if self.verbose else '',
            '--parallel', util.Interpolate('j%(prop:jobs)'),
        ]


class CompileDebAutobakeStep(Command):
    # TODO(cvicentiu) Implement this for Debian Autobake
    def __init__(self):
        ...
