import os

from twisted.application import service
from twisted.python.log import FileLogObserver, ILogObserver
from twisted.python.logfile import LogFile

from buildbot.master import BuildMaster

basedir = os.path.abspath(os.path.dirname(__file__))
log_basedir = "/var/log/buildbot/"

rotate_length = 20000000
max_rotated_files = 30
configfile = "master.cfg"

# Default umask for server
umask = None

# note: this line is matched against to check that this is a buildmaster
# directory; do not edit it.
application = service.Application('buildmaster')  # fmt: skip

logfile = LogFile.fromFullPath(
    os.path.join(log_basedir, "%s"),
    rotateLength=rotate_length,
    maxRotatedFiles=max_rotated_files,
)
application.setComponent(ILogObserver, FileLogObserver(logfile).emit)

m = BuildMaster(basedir, configfile, umask)
m.setServiceParent(application)
m.log_rotation.rotateLength = rotate_length
m.log_rotation.maxRotatedFiles = max_rotated_files
