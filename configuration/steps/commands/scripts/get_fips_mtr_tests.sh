#!/bin/bash


output_file=${1:-"fips_mtr_tests.txt"}


set +x

extract_test() {
local filepath="$1"

awk -F'/' -v path="$filepath" '
BEGIN {
    n = split(path, parts, "/")
    test = parts[n]
    sub(/\.test$/, "", test)
    dir1 = parts[n-1]
    if (dir1 == "t") {
    suite = parts[n-2]
    } else {
    suite = dir1
    }
    print suite "." test
}
'
}


# Extract all encryption tests
find mysql-test/suite/encryption -type f -name "*.test" | while read -r file; do
extract_test "$file" >> "$output_file"
done

# Extract all tests having SSL in their name
find mysql-test -name "*ssl*.test" | while read -r file; do
extract_test "$file" >> "$output_file"
done

# Extract all plugin tests
find plugin/**/* -name "*.test" | while read -r file; do
extract_test "$file" >> "$output_file"
done

# Extract all tests related to encoding, encryption, and hashing
grep -rliE --include="*.test" 'encode|des_encrypt|aes_encrypt|md5|sha[12]' mysql-test | while read -r file; do
extract_test "$file" >> "$output_file"
done

# Sort and remove duplicates
sort -u "$output_file" -o "$output_file"

# FIXME - Add the test back after MDEV-37209 is fixed
sed -i '/galera_3nodes.galera_garbd_backup/d' "$output_file"
# FIXME - Add the test back after MDEV-37257 is fixed
sed -i '/galera.galera_var_notify_ssl_ipv6/d' "$output_file"


cat "$output_file"