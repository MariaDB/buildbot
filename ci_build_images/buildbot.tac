import fnmatch
import os
import sys

from buildbot_worker.bot import Worker
from twisted.application import service
from twisted.python.log import FileLogObserver, ILogObserver

# setup worker
basedir = os.path.abspath(os.path.dirname(__file__))
application = service.Application('buildbot-worker')  # fmt: skip


application.setComponent(ILogObserver, FileLogObserver(sys.stdout).emit)
# and worker on the same process!
buildmaster_host = os.environ.get("BUILDMASTER", "localhost")
port = int(os.environ.get("BUILDMASTER_PORT", 9989))
workername = os.environ.get("WORKERNAME", "docker")
passwd = os.environ.get("WORKERPASS")

# delete the password from the environ so that it is not leaked in the log
blacklist = os.environ.get("WORKER_ENVIRONMENT_BLACKLIST", "WORKERPASS").split()
for name in list(os.environ.keys()):
    for toremove in blacklist:
        if fnmatch.fnmatch(name, toremove):
            del os.environ[name]

keepalive = 600
umask = None
maxdelay = 300
allow_shutdown = None
maxretries = 10

s = Worker(
    buildmaster_host,
    port,
    workername,
    passwd,
    basedir,
    keepalive,
    umask=umask,
    maxdelay=maxdelay,
    allow_shutdown=allow_shutdown,
    maxRetries=maxretries,
    unicode_encoding="utf-8",
)
s.setServiceParent(application)
