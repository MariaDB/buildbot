class CompilerCommand:
    def __init__(self, cc: str, cxx: str):
        assert isinstance(cc, str)
        assert isinstance(cxx, str)
        self.cc_ = cc
        self.cxx_ = cxx

    @property
    def cc(self):
        return self.cc_

    @property
    def cxx(self):
        return self.cxx_


class GCCCompiler(CompilerCommand):
    def __init__(self, version: str = None):
        if version:
            super().__init__(f"gcc-{version}", f"g++-{version}")
        else:
            super().__init__("gcc", "g++")


class ClangCompiler(CompilerCommand):
    def __init__(self, version: str = None):
        if version:
            super().__init__(cc=f"clang-{version}", cxx=f"clang++-{version}")
        else:
            super().__init__(cc="clang", cxx="clang++")


class MicrosoftCompiler(CompilerCommand):
    def __init__(self):
        super().__init__(cc="cl", cxx="cl++")


# TODO(cvicentiu) aocc, intel compiler.
