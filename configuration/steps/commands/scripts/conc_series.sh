#!/bin/bash
#
# Prints the C/C series (major.minor, e.g. 3.4) of a Connector/C source tree,
# read from the CPACK_PACKAGE_VERSION_MAJOR/MINOR lines of its CMakeLists.txt.
# Fails when it cannot read them.
#
# Usage: conc_series.sh <path to CMakeLists.txt>

set -euo pipefail

err() {
  echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')]: $*" >&2
}

main() {
  local cmake="$1"
  local re='^[[:space:]]*SET\(CPACK_PACKAGE_VERSION_(MAJOR|MINOR) ([0-9]+)\)'
  local major=""
  local minor=""
  local line

  if [[ ! -f "${cmake}" ]]; then
    err "Missing ${cmake}"
    exit 1
  fi

  while IFS= read -r line; do
    if [[ "${line}" =~ ${re} ]]; then
      case "${BASH_REMATCH[1]}" in
        MAJOR) major="${BASH_REMATCH[2]}" ;;
        MINOR) minor="${BASH_REMATCH[2]}" ;;
      esac
    fi
  done < "${cmake}"

  if [[ -z "${major}" || -z "${minor}" ]]; then
    err "Cannot read the C/C version" \
      "(CPACK_PACKAGE_VERSION_MAJOR/MINOR) from ${cmake}"
    exit 1
  fi
  echo "${major}.${minor}"
}

main "$@"
