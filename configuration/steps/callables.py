import re

from buildbot.process.buildstep import BuildStep


def needToTestSrpm(step: BuildStep) -> bool:
    """
    Any file in the ChangeSet that won't match the following regex
    can affect the results of a rebuild from the source RPM, thus,
    enabling the test.
    """
    for f in step.build.allFiles():
        if not re.search(
            "[^/]+\.(test|result|inc|cc|h|opt|c|cnf|rdiff|cpp|hpp|yy)$", f
        ):
            return True
    return False
