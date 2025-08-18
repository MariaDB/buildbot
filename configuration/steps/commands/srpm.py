from pathlib import PurePath

from configuration.steps.commands.base import BashScriptCommand


class SRPMInstallBuildDeps(BashScriptCommand):
    """
    A command to install build dependencies from a source RPM (SRPM) file.
    """

    def __init__(self, workdir: PurePath = PurePath(".")):
        dir_srpms = "srpms"
        args = [dir_srpms]
        super().__init__(
            script_name="srpm_install_build_deps.sh", workdir=workdir, args=args
        )
        self.name = "SRPM - Install Build Dependencies"


class SRPMRebuild(BashScriptCommand):
    """
    A command to rebuild the RPM's from a source RPM.
    """

    def __init__(self, jobs: int, workdir: PurePath = PurePath(".")):
        dir_srpms = "srpms"
        args = [dir_srpms, jobs]
        super().__init__(script_name="srpm_rebuild.sh", workdir=workdir, args=args)
        self.name = "SRPM - Rebuild RPMs"


class SRPMCompare(BashScriptCommand):
    """
    A command to compare the RPMs from the CI and rebuilt directories.
    """

    def __init__(self, workdir: PurePath = PurePath(".")):
        ci_rpms_dir = "rpms"
        rebuilt_rpms_dir = "../rpmbuild/RPMS"
        exclude_rpms = "MariaDB-compat*"
        args = [ci_rpms_dir, rebuilt_rpms_dir, exclude_rpms]
        super().__init__(script_name="srpm_compare.sh", workdir=workdir, args=args)
        self.name = "SRPM - Compare RPMs"
