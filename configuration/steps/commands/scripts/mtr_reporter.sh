#!/bin/bash

set -euo pipefail

# Input variables
BASE_URL="$1"        # e.g., 100.64.101.1:9990
BRANCH="$2"
REVISION="$3"
PLATFORM="$4"
BBNUM="$5"
DIR="$6"             # Base directory containing either .xml files OR component/log/stdout.log
CONTENT_KIND="$7"    # "xml" or "log"
DRY_RUN="${8:-0}"    # "1" = print curl commands only, "0" = actually run (default)

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

# Validate mode inputs early
case "$CONTENT_KIND" in
  xml|log) ;;
  *) err "Error: CONTENT_KIND must be 'xml' or 'log' (got: '$CONTENT_KIND')" ;;
esac

case "$DRY_RUN" in
  0|1) ;;
  *) err "Error: DRY_RUN must be 0 or 1 (got: '$DRY_RUN')" ;;
esac

# Step 1: Health check before uploads (skip if dry run)
command -v curl >/dev/null || err "curl not found"

if [[ "$DRY_RUN" == "1" ]]; then
  bb_log_info "DRY RUN enabled: skipping health check and uploads will not be executed."
else
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
fi

# Step 2: Validate directory
if [[ ! -d "$DIR" ]]; then
  err "Error: directory '$DIR' does not exist"
fi

# Step 3: Discover files based on content kind
shopt -s nullglob
FILES=()
if [[ "$CONTENT_KIND" == "xml" ]]; then
  FILES=("$DIR"/*.xml)
else
  # stdout.log in: <DIR>/<component>/log/stdout.log
  FILES=("$DIR"/*/log/stdout.log)
fi
shopt -u nullglob

if (( ${#FILES[@]} == 0 )); then
  if [[ "$CONTENT_KIND" == "xml" ]]; then
    err "Error: no .xml files found in directory '$DIR'"
  else
    err "Error: no stdout.log files found under '$DIR' (expected: <component>/log/stdout.log)"
  fi
fi

# Helper: print an argv array as a shell-escaped command (safe for copy/paste)
print_cmd() {
  local -a argv=( "$@" )
  printf '%q ' "${argv[@]}"
  printf '\n'
}

# Step 4: Upload files and track failures
ANY_FAILED=0

for FILE in "${FILES[@]}"; do
  BASENAME=""
  MIME_TYPE=""

  if [[ "$CONTENT_KIND" == "xml" ]]; then
    BASENAME="$(basename "$FILE" .xml)"
    MIME_TYPE="application/xml"
  else
    COMPONENT_DIR="$(dirname "$(dirname "$FILE")")"  # .../<component>
    BASENAME="$(basename "$COMPONENT_DIR")"
    MIME_TYPE="text/plain"
  fi

  bb_log_info "Preparing upload for $FILE (typ=$BASENAME)..."

  CURL_CMD=(
    curl
    --max-time 120
    --connect-timeout 10
    --fail-with-body
    -X POST "$UPLOAD_URL"
    -F "branch=${BRANCH}"
    -F "revision=${REVISION}"
    -F "platform=${PLATFORM}"
    -F "bbnum=${BBNUM}"
    -F "typ=${BASENAME}"
    -F "file=@${FILE};type=${MIME_TYPE}"
  )

  if (( DRY_RUN == 1 )); then
    bb_log_info "DRY RUN: would execute:"
    print_cmd "${CURL_CMD[@]}"
    continue
  fi

  if ! "${CURL_CMD[@]}"; then
    bb_log_info "Upload failed for $FILE"
    ANY_FAILED=1
  else
    bb_log_info "Upload succeeded for $FILE"
  fi
done

# Step 5: Final result
if (( DRY_RUN == 1 )); then
  bb_log_info "DRY RUN complete: no network calls were made."
elif ((ANY_FAILED != 0 )); then
  err "One or more uploads failed."
else
  bb_log_info "All uploads succeeded."
fi
