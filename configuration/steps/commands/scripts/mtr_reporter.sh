#!/bin/bash

set -euo pipefail

# Input variables
BASE_URL="$1"     # e.g., 100.64.101.1:9990
BRANCH="$2"
REVISION="$3"
PLATFORM="$4"
BBNUM="$5"
DIR="$6"          # Directory containing .xml files

err() {
  set +x
  echo >&2 "ERROR: $*"
  exit 1
}

bb_log_info() {
  set +x
  echo >&1 "INFO: $*"
  set -x
}

UPLOAD_URL="${BASE_URL}/upload-test-results/"
HEALTH_URL="${BASE_URL}/health"

# Step 1: Health check before uploads
command -v curl >/dev/null || err "curl not found"
bb_log_info "Checking service health at $HEALTH_URL..."
if ! curl "$HEALTH_URL" \
  --max-time 5 \
  --retry 3 \
  --retry-max-time 0 \
  --retry-delay 5 \
  --retry-connrefused \
  --fail-with-body; then
    err "Service health check failed. Aborting uploads."
fi
bb_log_info "Service is healthy. Proceeding with uploads."

# Step 2: Validate directory
if [[ ! -d "$DIR" ]]; then
  err "Error: directory '$DIR' does not exist"
fi

# Step 3: Find XML files
shopt -s nullglob
XML_FILES=("$DIR"/*.xml)
shopt -u nullglob

if (( ${#XML_FILES[@]} == 0 )); then
  err "Error: no .xml files found in directory '$DIR'"
fi

# Step 4: Upload files and track failures
ANY_FAILED=0

for FILE in "${XML_FILES[@]}"; do
  # Extract filename without extension for 'typ'
  BASENAME="$(basename "$FILE" .xml)"
  bb_log_info "Uploading $FILE (typ=$BASENAME)..."

  if ! curl --max-time 120 --connect-timeout 10 --fail-with-body \
    -X POST "$UPLOAD_URL" \
    -F "branch=${BRANCH}" \
    -F "revision=${REVISION}" \
    -F "platform=${PLATFORM}" \
    -F "bbnum=${BBNUM}" \
    -F "typ=${BASENAME}" \
    -F "file=@${FILE};type=application/xml"; then
      bb_log_info "Upload failed for $FILE"
      ANY_FAILED=1
  else
    bb_log_info "Upload succeeded for $FILE"
  fi
done

# Step 5: Final result
if ((ANY_FAILED != 0 )); then
  err "One or more uploads failed."
else
  bb_log_info "All uploads succeeded."
fi
