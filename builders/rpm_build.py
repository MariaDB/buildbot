from steps.cmake.compilers import GCCCompiler
from steps.cmake.generator import CMakeGenerator
from steps.cmake.options import CMAKE, BuildType, CMakeOption
from steps.configure import ConfigureMariaDBCMake
from steps.compile import CompileMakeCommand
from steps.fetch_file import FetchTarball

from .base import BaseBuilder
from .infra.runtime import DockerConfig, InContainerBuildSequence

class MTRTest:
    ...

class RPMBaseBuilder(BaseBuilder):
    def __init__(self, name: str, config: DockerConfig):
        super().__init__(name)

        self.add_sequence(
            InContainerBuildSequence([
                FetchTarball('https://ci.mariadb.org'),
                ConfigureMariaDBCMake(
                    'Debug Build',
                    cmake_generator=CMakeGenerator(
                        compiler=GCCCompiler(),
                        use_ccache=True,
                        flags=[
                            CMakeOption(CMAKE.BUILD_TYPE, BuildType.DEBUG),
                        ]),
                ),
                CompileMakeCommand(),
                # MTR Step
                MTRTest(type=MTRTest.Normal),
                MTRTest(type=MTRTest.Galera),
                MTRTest(type=MTRTest.S3),
                MTRTest(type=MTRTest.RocksDB),
                MTRTest(type=MTRTest.OptimizerTrace),
                SavePackages(),
            ])
        )
