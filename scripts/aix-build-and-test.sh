#!/bin/sh

set -xeuv

build_deps() {
  # MDEV-32815 - awaiting for 10.1.1+ bump.
  # manually remove install directory when changeing version
  # v=9.1.0,9.0.0,8.1.1 - fails to build
  v=8.0.1
  wget https://github.com/fmtlib/fmt/archive/refs/tags/${v}.tar.gz -O - | tar -zxf -
  rm -rf build-fmt
  mkdir -p build-fmt
  cd build-fmt
  cmake -DCMAKE_CXX_COMPILER=g++-11 -DCMAKE_COMPILER_IS_GNUCXX=0 \
	  -DCMAKE_INSTALL_PREFIX="$HOME"/inst-fmt \
	  -DFMT_DOC=OFF -DFMT_TEST=OFF \
	  ../fmt-$v/
  cmake --build .
  cmake --install .
  cd ..
  rm -rf build-fmt
}

build() {
  if [ ! -d "${HOME}"/inst-fmt ]; then
    build_deps
  fi
  source=$1
  mkdir -p build
  cd build
  /opt/bin/ccache --zero-stats
  cmake ../"$source" -DCMAKE_BUILD_TYPE="$2" \
    -DCMAKE_C_LAUNCHER=/opt/bin/ccache \
    -DCMAKE_CXX_LAUNCHER=/opt/bin/ccache \
    -DCMAKE_C_COMPILER=gcc-11 \
    -DCMAKE_CXX_COMPILER=g++-11 \
    -DCMAKE_AR=/usr/bin/ar \
    -DCMAKE_PREFIX_PATH=/opt/freeware/ \
    -DCMAKE_REQUIRED_LINK_OPTIONS=-L/opt/freeware/lib \
    -DCMAKE_REQUIRED_FLAGS=-I\ /opt/freeware/include \
    -DPLUGIN_OQGRAPH=NO \
    -DWITH_UNIT_TESTS=NO \
    -DPLUGIN_S3=NO \
    -DPLUGIN_CONNECT=NO \
    -DPLUGIN_SPIDER=NO \
    -DPLUGIN_WSREP_INFO=NO \
    -DLIBFMT_INCLUDE_DIR="$HOME"/inst-fmt/include \
    -DCMAKE_LIBRARY_PATH="$HOME"/inst-fmt/lib \
    -Dhave_C__Wl___as_needed= \
    -DPLUGIN_AUTH_GSSAPI=NO -DPLUGIN_TYPE_MYSQL_JSON=NO
  make -j"$(("$jobs" * 2))"
  /opt/bin/ccache --show-stats
}

mariadbtest() {
  cat <<EOF >../unstable-tests
type_test.type_test_double   : unknown reason
plugins.server_audit         : unknown reasons
innodb.log_file_name         : Unknown but frequent reasons
main.cli_options_force_protocol_not_win : unknown reasons
type_inet.type_inet6         : AIX incorrect IN6_IS_ADDR_V4COMPAT implementation (reported)
main.func_json_notembedded   : machine too fast sometimes - bb-10.6-danielblack-MDEV-27955-postfix-func_json_notembedded
binlog_encryption.rpl_typeconv : timeout on 2 minutes, resource, backtrace is just on poll loop
rpl.rpl_typeconv : timeout on 2 minutes, resource, backtrace is just on poll loop
rpl.rpl_row_img_blobs : timeout on 2 minutes, resource, backtrace is just on poll loop
main.mysql_upgrade : timeout on 2 minutes, resource, backtrace is just on poll loop
main.mysql_client_test_comp : too much memory when run in parallel (8 seems to work)
federated.* : really broken, can't load plugin
encryption.innodb-redo-nokeys : [ERROR] InnoDB: Missing FILE_CHECKPOINT at 1309364 between the checkpoint 51825 and the end 1374720
innodb.insert_into_empty : ER_ERROR_DURING_COMMIT "Operation not permitted" -> "Not Owner"
mariabackup.incremental_compressed : mysqltest: At line 19: query 'INSTALL SONAME 'provider_snappy'' failed: <Unknown> (2013): Lost connection to server during query
innodb.innodb-page_compression_lz4 : plugins sigh
innodb.innodb-page_compression_lzma : plugins sigh
mariabackup.compression_providers_loaded : plugins sigh
mariabackup.compression_providers_unloaded : plugins sigh
plugins.compression : plugins sigh
innodb.compression_providers_loaded : plugins sigh
plugins.test_sql_service : plugins sigh
plugins.password_reuse_check : plugins sigh
plugins.compression_load : plugins sigh
innodb.innodb_28867993 : need supression -[ERROR] InnoDB: File ./ib_logfile2: 'delete' returned OS error 201.
rpl.rpl_row_img_sequence_min : MDEV-30222 fork failed sleep 1 second and redo: Resource temporarily unavailable  At line 42: popen("\$MYSQL_BINLOG \$mysqld_datadir/\$binlog_filename -vv > \$assert_file", "r") failed
rpl.rpl_xa_empty_transaction : NDEV-30222
rpl.rpl_row_img_sequence_noblob : NDEV-30222
main.mysql_client_test : mysqltest: At line 27: exec of '/home/buildbot/aix/build/build/tests/mysql_client_test - possibly LIBPATH related
EOF
  case "${1:-mariadb-10.5.10}" in
	  mariadb-10.[56].*)
		  echo "innodb.log_buffer_size : Marko request" >> ../unstable-tests
		  ;;
  esac
  # for saving logs
  ln -s build/mysql-test .
  mysql-test/mysql-test-run.pl --verbose-restart --force --retry=3 --max-save-core=1 --max-save-datadir=10 \
    --max-test-fail=20 --testcase-timeout=2 --parallel="$jobs" --skip-test-list="$PWD/../unstable-tests"

}

clean() {
  ls -ad "$@" || echo "not there I guess"
  rm -rf "$@" 2>/dev/null
  rm -r /buildbot/mysql_logs.html 2>/dev/null || true
}

export TMPDIR="$HOME/tmp"
# gcc-10 paths found by looking at nm /opt/freeware/.../libstdc++.a | grep {missing symbol}
export LIBPATH=/opt/freeware/lib/gcc/powerpc-ibm-aix7.1.0.0/11/pthread/:/opt/freeware/lib/gcc/powerpc-ibm-aix7.1.0.0/11:/usr/lib:"$PWD/build/libmariadb/libmariadb/"

jobs=${4:-12}

stage=$1
shift
case $stage in
  build)
    build "$@"
    ;;
  test)
    if [ "$#" -ge 1 ]; then
      mariadbtest "$@"
    else
      mariadbtest
    fi
    ;;
  clean)
    clean mariadb* build* mysql-test /mnt/packages/* /buildbot/logs/*
    ;;
esac
