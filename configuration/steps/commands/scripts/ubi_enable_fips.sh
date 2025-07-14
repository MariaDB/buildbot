#!/bin/bash

# Check if OpenSSL is installed
if ! command -v openssl &> /dev/null; then
    echo "OpenSSL is not installed."
    exit 1
fi

# Enable FIPS mode in RedHat OpenSSL
sed -i -e '/\[ evp_properties \]/a default_properties = fips=yes' \
    -e '/opensslcnf.config/a .include = /etc/crypto-policies/back-ends/openssl_fips.config' \
    -e '/\[provider_sect\]/a fips = fips_sect' \
    /etc/pki/tls/openssl.cnf


# List providers. If FIPS is not listed, it may not be enabled.
if ! openssl list -providers | grep -q 'fips'; then
    echo "FIPS provider is not enabled."
    exit 1
fi

# If FIPS is enabled then generating a hash with MD5 should fail
if openssl dgst -md5 /dev/null &> /dev/null; then
    echo "FIPS mode is not enabled."
    exit 1
else
    echo "FIPS mode is enabled."
    exit 0
fi