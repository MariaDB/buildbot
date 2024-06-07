#!/usr/bin/env bash

NPROC="%(prop:jobs)s"
PREFIX=~/mariadb-bin

LEIN_OPTIONS="run test --db maria-docker --nodes localhost --concurrency ${NPROC} --rate 1000 --time-limit 60 --key-count 40 --no-ssh=true --innodb-strict-isolation=true"

cd ../jepsen-mysql
echo "===========Append serializable============="
../lein $LEIN_OPTIONS -w append -i serializable
echo "===========Append repeatable-read============="
../lein $LEIN_OPTIONS -w append -i repeatable-read
echo "===========Append read-committed============="
../lein $LEIN_OPTIONS -w append -i read-committed
echo "===========Append read-uncommitted============="
../lein $LEIN_OPTIONS -w append -i read-uncommitted

echo "===========Non-repeatable read serializable============="
../lein $LEIN_OPTIONS -w nonrepeatable-read -i serializable
echo "===========Non-repeatable repeatable-read============="
../lein $LEIN_OPTIONS -w nonrepeatable-read -i repeatable-read

echo "===========mav serializable============="
../lein $LEIN_OPTIONS -w mav -i serializable
echo "===========mav repeatable-read============="
../lein $LEIN_OPTIONS -w mav -i repeatable-read