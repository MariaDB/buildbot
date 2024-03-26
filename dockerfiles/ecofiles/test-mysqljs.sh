#!/bin/bash

set -xeuvo pipefail

cd /code
[ -d mysql ] || git clone https://github.com/mysqljs/mysql
cd mysql
id
ls -la
chmod -R go-w .
chown -R root: .
git clean -dfx
git pull --tags
if [ $# -gt 0 ]
then
  if [ ! -d ../"$1" ]
  then
    git worktree add ../"$1" "$1"
  fi
  cd ../"$1"
  chmod -R go-w .
  chown -R root: .
  # this is right for tags, not for branches yet
  git checkout "$1"
fi
git checkout -- .


# Unit tests

# fix for ERR_SSL_EE_KEY_TOO_SMALL (1024 bit test/fixtures/server.key)
rm -f test/unit/connection/test-connection-ssl-reject.js \
	 test/unit/connection/test-connection-ssl-ignore.js \
	 test/unit/connection/test-connection-ssl-ciphers.js \
	 test/unit/connection/test-connection-ssl.js \
	 test/unit/connection/test-connection-ssl-max-version-accept.js \
	 test/unit/connection/test-connection-ssl-max-version-reject.js \
	 test/unit/connection/test-connection-ssl-min-version-accept.js \
	 test/unit/connection/test-connection-ssl-min-version-reject.js \
	 test/integration/connection/test-server-timeout-disconnect.js \
	 test/integration/connection/test-statistics.js \
	 test/integration/connection/test-load-data-infile-disable.js

#npm install -g npm@8.5.5
npm install
# Run the unit tests (probably should be controlled with worker variable)
# If unit==1 run unit test else run integration test
cd ./test
FILTER=unit npm test

cd ..

# Integration tests

VERSION=$(/usr/local/mariadb/bin/mysql -u root --column-names=0 -B -e "SELECT VERSION()")

case "${VERSION}" in
10\.[5-9]\.*)
# awaiting fix https://github.com/mysqljs/mysql/pull/2442
	sed -i -e '/flush_tables/d' test/integration/connection/test-statistics.js
# From https://github.com/mysqljs/mysql/pull/2442/files#diff-5979044946698d18a2cdc979898085cdddf5f9911974e8e7a4476efd25c07d82R35
# ER_LOAD_INFILE_CAPABILITY_DISABLED
	sed -i -e "s/err.code, 'ER_NOT_ALLOWED_COMMAND'/err.errno, 4166/" test/integration/connection/test-load-data-infile-disable.js
	sed -i -e 's/PROTOCOL_CONNECTION_LOST/ECONNRESET/g' test/integration/connection/test-server-timeout-disconnect.js
esac

cd ./test
# Run integration test - we are more interested in this!
/usr/local/mariadb/bin/mysql -u root -e "CREATE DATABASE IF NOT EXISTS node_mysql_test"
MYSQL_HOST=localhost MYSQL_PORT=3306 MYSQL_DATABASE=node_mysql_test MYSQL_USER=root MYSQL_PASSWORD='' FILTER=integration npm test

