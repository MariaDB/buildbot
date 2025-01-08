# -*- python -*-
# ex: set filetype=python:
import os

from twisted.application import service
from twisted.python.log import FileLogObserver, ILogObserver
from twisted.python.logfile import LogFile

from buildbot.master import BuildMaster

# This buildbot.tac file is a basis for all "autogen" masters.
# The folder structure for autogen masters is:
#
# autogen
# └── aarch64-master-0
#     ├── buildbot.tac
#     ├── master.cfg
#     ├── master-config.yaml
#     └── master-private.cfg
#
# Thus basedir is two levels below this file"s position.
buildbot_tac_dir = os.path.abspath(os.path.dirname(__file__))
basedir = os.path.abspath(f"{buildbot_tac_dir}/../../")

# Hard coded as it runs in containers.
# TODO(cvicentiu) this should come as an environment variable.
log_basedir = "/var/log/buildbot"

rotateLength = 20000000
maxRotatedFiles = 30
# Last two directories. autogen and <master-name>
cfg_from_basedir = os.path.normpath(buildbot_tac_dir).split(os.sep)[-2:] + [
    "master.cfg"
]

configfile = os.path.join(*cfg_from_basedir)
# Default umask for server
umask = None

# note: this line is matched against to check that this is a buildmaster
# directory; do not edit it.
application = service.Application("buildmaster")  # fmt: skip

logfile = LogFile.fromFullPath(
    os.path.join(log_basedir, "%s"),
    rotateLength=rotateLength,
    maxRotatedFiles=maxRotatedFiles,
)
application.setComponent(ILogObserver, FileLogObserver(logfile).emit)

m = BuildMaster(basedir, configfile, umask)
m.setServiceParent(application)
m.log_rotation.rotateLength = rotateLength
m.log_rotation.maxRotatedFiles = maxRotatedFiles
