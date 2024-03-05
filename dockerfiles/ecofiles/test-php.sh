#!/bin/bash
# curl url | bash -s [branch] [buildopt] [additional build options...]

set -xeuvo pipefail

declare -A buildopts=(
	[mysqlnd]='--enable-mysqlnd --with-mysqli=mysqlnd --with-pdo-mysql=mysqlnd'
	[mariadbclient]='--with-mysqli --with-pdo-mysql=/usr/local/mariadb'
)

branch=${1:-master}
shift || echo "Using default branch '$branch'"
opt=${1:-mysqlnd}
shift || echo "Using default option '$opt'"

if [ -z "${buildopts[$opt]}" ]; then
   echo "Unsupported build option $opt"
   exit 1
fi

# variable needed to make mysqli_expire_password test pass
# only exists on 10.4+
/usr/local/mariadb/bin/mysql -u root -e '/*M!100403 set global disconnect_on_expired_password=1 */' \
	|| :
# pam test - https://github.com/php/php-src/pull/6667
/usr/local/mariadb/bin/mysql -u root -e "INSTALL SONAME 'auth_pam'" \
	|| :


export MYSQL_TEST_DB=test
export MYSQL_TEST_HOST=localhost
export MYSQL_TEST_PORT=3306
export MYSQL_TEST_SOCKET=/tmp/mysql.sock
export MYSQL_TEST_USER=root
export MYSQL_TEST_PASSWD=letmein

/usr/local/mariadb/bin/mysql -u root -e "set password=password('$MYSQL_TEST_PASSWD')" \
	|| :
# Controlling Environment variables from ./ext/mysqli/tests/connect.inc
# MYSQL_TEST_{HOST,PORT,USER,PASSWD,DB
# ENGINE,SOCKET
# CONNECT_FLAGS - integer for mysqli_real_connect

export PDO_MYSQL_TEST_HOST="${MYSQL_TEST_HOST}"
export PDO_MYSQL_TEST_USER="${MYSQL_TEST_USER}"
export PDO_MYSQL_TEST_PASS="${MYSQL_TEST_PASSWD}"
export PDO_MYSQL_TEST_SOCKET="${MYSQL_TEST_SOCKET}"
export PDO_MYSQL_TEST_DSN="mysql:host=${PDO_MYSQL_TEST_HOST};dbname=${MYSQL_TEST_DB};socket=${PDO_MYSQL_TEST_SOCKET}"
#
# ./ext/pdo_mysql/tests/mysql_pdo_test.inc
# PDO_MYSQL_TEST_DSN, = mysql:host=localhost;dbname=test
# PDO_MYSQL_TEST_USER
# PDO_MYSQL_TEST_PASS
# PDOTEST_ATTR
# PDO_MYSQL_TEST_ENGINE


cd /code

chown -R root: .

# https://stackoverflow.com/questions/3258243/check-if-pull-needed-in-git
UPSTREAM='@{u}'
git_update_refs()
{
  LOCAL=$(git rev-parse @)
  REMOTE=$(git rev-parse "$UPSTREAM")
  BASE=$(git merge-base @ "$UPSTREAM")
  if [ $LOCAL = $REMOTE ]; then
    git checkout -f HEAD
    echo "Up-to-date"
  elif [ $LOCAL = $BASE ]; then
    echo "Need to pull"
    git clean -dfX
    git clean -dfx
    git pull
    ./buildconf
  elif [ $REMOTE = $BASE ]; then
    echo "Need to push"
  else
    echo "Diverged"
  fi
}

if [ -d master ]
then
  cd master
  git remote update
else
  git clone https://github.com/php/php-src.git master
  cd master
fi
git_update_refs

codedir=/code/$branch

if [ "$branch" != "master" ]
then
  if [ -d "$codedir" ]
  then
    ( cd "$codedir"; git_update_refs )
  else
    mkdir -p "$codedir"
    git worktree add "$codedir" "$branch"
    ( cd "$codedir"; ./buildconf )
  fi
fi

echo
echo "BRANCH: $branch"
echo "BUILD: $opt"

builddir="/build/${branch}-${opt}"
mkdir -p "$builddir"
cd "$builddir"

configure()
{
  # word splitting needed on buildopts
  # shellcheck disable=SC2086
  "$codedir"/configure --enable-debug \
                 ${buildopts[$opt]} "$@" \
                 --with-mysql-sock=/tmp/mysql.sock || cat config.log
}

if [ "$codedir"/configure -nt config.log ]
then
  configure "$@"
fi
make -j "$(nproc)"
# Looking for error make: *** No rule to make target '/code/master/Zend/zend_rc_debug.h', needed by 'ext/opcache/ZendAccelerator.lo'.  Stop.
# This can occur during some dependency changes not fully undertood by make. Clear it out and do a full rebuild.
if (( $? == 2 )); then
  echo clear and retry
  rm -rf -- *
  configure "$@"
  make -j "$(nproc)"
fi

echo
echo Testing...
echo

declare -a mysqlifailtests
declare -a pdofailtests

case "${branch}" in
	PHP-7\.[12])
		mysqlifailtests+=( mysqli_get_client_stats ) # 7.3 fixed
		mysqlifailtests+=( 057 )
		mysqlifailtests+=( mysqli_pconn_max_links )
		mysqlifailtests+=( mysqli_stmt_bind_param_many_columns )
		mysqlifailtests+=( mysqli_report )
		mysqlifailtests+=( bug34810 )
		mysqlifailtests+=( mysqli_class_mysqli_interface )
		mysqlifailtests+=( mysqli_reap_async_query )
		mysqlifailtests+=( mysqli_character_set ) # 001+ [008 + utf8mb3] [2019] Invalid characterset or character set not supported
		mysqlifailtests+=( mysqli_options ) # 013+ [009] Setting charset name 'utf8mb3' has failed
		mysqlifailtests+=( mysqli_set_charset ) # 001+ [017] Cannot set character set to 'utf8mb3', [2019] Invalid characterset or character set not supported \n002+
		;&
	PHP-7\.3)
		mysqlifailtests+=( mysqli_stmt_get_result_metadata_fetch_field ) # https://github.com/php/php-src/pull/6484 - fixed 7.4
		;&
	PHP-7\.4)
		mysqlifailtests+=( 063 ) # fixed in 8.0 at least
		mysqlifailtests+=( mysqli_change_user_new ) # at least 8.0 (not 7.4)
		;&
	PHP-8\.0)
		pdofailtests+=( bug_38546 )
		;&
	PHP-8\.1)
		mysqlifailtests+=( mysqli_real_connect mysqli_real_connect_pconn mysqli_connect_oo mysqli_report ) # https://github.com/php/php-src/commit/b6b4a628a5009024f9abca664f6a25d64b6f64d6
		;&
	master)
		mysqlifailtests+=( mysqli_reap_async_query_error mysqli_execute_query.phpt ) # https://github.com/php/php-src/pull/10029
		mysqlifailtests+=( mysqli_connect ) # Using Password - like b6b4a628a5009024f9
		#mysqlifailtests+=( mysqli_change_user ) # will below 3 - fail on 7.1, not mdb-10.2. TODO
		#mysqlifailtests+=( mysqli_change_user_old ) # TODO
		#mysqlifailtests+=( mysqli_change_user_oo ) # TODO
		#mysqlifailtests+=( mysqli_class_mysqli_properties_no_conn ) # TODO
		#pdofailtests+=( pdo_mysql_prepare_load_data ) # 8.0, not 7.4 TODO investigate
		#pdofailtests+=( pdo_mysql_attr_oracle_nulls ) # 8.0, not 7.4. TODO investigate
		#mysqlifailtests+=( mysqli_debug )
		#mysqlifailtests+=( mysqli_debug_append )
		#mysqlifailtests+=( mysqli_debug_control_string )
		#mysqlifailtests+=( mysqli_debug_mysqlnd_control_string )
		#mysqlifailtests+=( mysqli_debug_mysqlnd_only )
		#mysqlifailtests+=( mysqli_class_mysqli_interface ) # 8.0, not 7.1
		#mysqlifailtests+=( mysqli_auth_pam ) # Access denied for user 'pamtest'@'localhost' (using password: NO) - but password is.

esac

GLOBIGNORE=

for f in "${mysqlifailtests[@]}"
do
  GLOBIGNORE="$GLOBIGNORE:$codedir/ext/mysqli/tests/$f.phpt"
done
for f in "${pdofailtests[@]}"
do
  GLOBIGNORE="$GLOBIGNORE:$codedir/ext/pdo_mysql/tests/$f.phpt"
done
echo $GLOBIGNORE

mkdir -p /tmp/s /tmp/t

# -j$(nproc) not in 7.3 - didn't significantly parallize anyway
TEST_PHP_EXECUTABLE=./sapi/cli/php ./sapi/cli/php "$codedir"/run-tests.php \
       --temp-source /tmp/s --temp-target /tmp/t  --show-diff \
       "$codedir"/ext/mysqli/tests/*phpt \
       "$codedir"/ext/pdo_mysql/tests/*phpt
