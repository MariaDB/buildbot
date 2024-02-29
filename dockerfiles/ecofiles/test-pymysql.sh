#!/bin/bash

set -xeuvo pipefail

cd /code
[ -d PyMySQL ] || git clone https://github.com/PyMySQL/PyMySQL.git
cd PyMySQL
git clean -dfx
git checkout main
git pull --tags
if [ $# -gt 0 ]
then
  if [ ! -d ../"$1" ]
  then
    git worktree add ../"$1" "$1"
  fi
  cd ../"$1"
  # this is right for tags, not for branches yet
  git checkout "$1"

  /usr/local/mariadb/bin/mysql --comments -u root <<EOF
  SELECT c INTO @install_unix FROM (SELECT 'INSTALL SONAME "auth_socket"' AS c FROM DUAL WHERE NOT EXISTS (select 1 from information_schema.plugins where
  PLUGIN_NAME='unix_socket') UNION SELECT 'SELECT 1/* nothing */' FROM information_schema.plugins where PLUGIN_NAME='unix_socket') AS dodont ;
  execute immediate @install_unix;

  create database if not exists test1 DEFAULT CHARACTER SET utf8mb4;
  create database if not exists test2 DEFAULT CHARACTER SET utf8mb4;
  create user if not exists test2 identified by 'some password';
  grant all on test2.* to test2;
  create user if not exists test2@localhost identified by 'some password';
  grant all on test2.* to test2@localhost;
  drop user if exists buildbot@locahost;
EOF

  export USER=buildbot
  # Both passwd and password are aliased to the same, so this isn't an error in the below configuration.
  # passwd and db where deprecated in PyMySQL f5cbb6dea0a77c5e3055a299ed9a5b458c29cb12 (v1.0.1)
  # assume versioned tests are the old one(s)
  cat > pymysql/tests/databases.json <<EOF
  [
      {"host": "localhost", "unix_socket": "/tmp/mysql.sock", "user": "root", "passwd": "", "db": "test1", "use_unicode": true, "local_infile": true},
      {"host": "127.0.0.1", "port": 3306, "user": "test2", "password": "some password", "db": "test2" }
  ]
EOF

  # Socket auth failing due to user existing?
  pytest -v -k 'not testSocketAuth' pymysql

  if [ -f tests/test_mariadb_auth.py ]
  then
    pytest -v tests/test_mariadb_auth.py pymysql
  fi

else
  # main branch.
  /usr/local/mariadb/bin/mysql --comments -u root < ci/docker-entrypoint-initdb.d/init.sql
  /usr/local/mariadb/bin/mysql --comments -u root < ci/docker-entrypoint-initdb.d/mariadb.sql

  cp ci/docker.json pymysql/tests/databases.json

  export USER=buildbot

  # test_auth is MySQL sha256password tests
  pytest -v -k 'not test_auth' pymysql

fi
