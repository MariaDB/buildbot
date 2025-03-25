# -*- python -*-
# ex: set filetype=python:
from pathlib import Path

from twisted.application import service
from twisted.python.log import FileLogObserver, ILogObserver
from twisted.python.logfile import LogFile

from buildbot.master import BuildMaster

# This buildbot.tac file is a basis for non-autogen masters.
# The folder structure for autogen masters is:
#
# <srcdir>
# └── master-xxxxxx
#     ├── buildbot.tac
#     ├── master.cfg
#     ├── master-config.yaml
#     └── master-private.cfg
#
# Thus basedir is one levels below this file's position.
buildbot_tac_dir = Path(__file__).resolve().parent
basedir = buildbot_tac_dir.parent

# Hard coded as it runs in containers.
# TODO(cvicentiu) this should come as an environment variable.
log_basedir_path = Path("/var/log/buildbot/")
log_basedir = log_basedir_path.as_posix()  # Kept in case buildbot uses it.

rotateLength = 10000000
maxRotatedFiles = 30

master_name = buildbot_tac_dir.name
# Last two directories. autogen and <master-name>
cfg_from_basedir = (buildbot_tac_dir / "master.cfg").relative_to(basedir)

configfile = cfg_from_basedir.as_posix()

# Default umask for server
umask = None

# note: this line is matched against to check that this is a buildmaster
# directory; do not edit it.
application = service.Application('buildmaster')  # fmt: skip

# This logfile is monitored. It must end in .log.
logfile = LogFile.fromFullPath(
    str(log_basedir_path / f"{master_name}.log"),
    rotateLength=rotateLength,
    maxRotatedFiles=maxRotatedFiles,
)
application.setComponent(ILogObserver, FileLogObserver(logfile).emit)

m = BuildMaster(str(basedir), configfile, umask)
m.setServiceParent(application)
m.log_rotation.rotateLength = rotateLength
m.log_rotation.maxRotatedFiles = maxRotatedFiles
