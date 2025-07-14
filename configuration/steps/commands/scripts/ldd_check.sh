#!/bin/bash
set -euo pipefail

echo "Checking dynamic library dependencies..."

# bash ldd_check.sh "/usr/bin/curl:libssl.so.1.1,libcrypto.so.1.1" "./myapp:libstdc++.so.6,libm.so.6"
for entry in "$@"; do
    binary="${entry%%:*}"
    libs="${entry#*:}"

    echo "Checking $binary..."
    [[ -f "$binary" ]] || { echo "Missing binary: $binary"; exit 1; }

    IFS=',' read -ra lib_array <<< "$libs"
    for lib in "${lib_array[@]}"; do
        if ldd "$binary" | grep -q "$lib"; then
            echo "$lib found in $binary"
        else
            echo "$lib NOT found in $binary"
            exit 1
        fi
    done
done

echo "All checks passed."
