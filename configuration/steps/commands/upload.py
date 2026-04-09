from buildbot.plugins import steps, util


class FileUpload:
    def __init__(self, workersrc, masterdest, mode, url, doStepIf=True):
        self.workersrc = workersrc
        self.masterdest = masterdest
        self.mode = mode
        self.url = url
        self.doStepIf = doStepIf

    def generate(self):
        return steps.FileUpload(
            workersrc=util.Interpolate(self.workersrc),
            masterdest=util.Interpolate(self.masterdest),
            mode=self.mode,
            url=util.Interpolate(self.url),
            doStepIf=self.doStepIf,
        )
