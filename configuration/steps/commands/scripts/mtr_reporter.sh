#!/bin/bash

set -euo pipefail

# Input variables
BASE_URL="$1"     # e.g., 100.64.101.1:9990
BRANCH="$2"
REVISION="$3"
PLATFORM="$4"
BBNUM="$5"
DIR="$6"          # Directory containing .xml files

UPLOAD_URL="${BASE_URL}/upload-test-results/"
HEALTH_URL="${BASE_URL}/health"

# Step 1: Health check before uploads
echo "Checking service health at $HEALTH_URL..."
if ! curl "$HEALTH_URL" \
  --max-time 5 \
  --retry 3 \
  --retry-max-time 0 \
  --retry-delay 5 \
  --retry-connrefused \
  --fail-with-body; then
    echo "Service health check failed. Aborting uploads."
    exit 1
fi
echo "Service is healthy. Proceeding with uploads."

# Step 2: Validate directory
if [[ ! -d "$DIR" ]]; then
  echo "Error: directory '$DIR' does not exist"
  exit 1
fi

# Step 3: Find XML files
shopt -s nullglob
XML_FILES=("$DIR"/*.xml)
shopt -u nullglob

if [[ ${#XML_FILES[@]} -eq 0 ]]; then
  echo "Error: no .xml files found in directory '$DIR'"
  exit 1
fi

# Step 4: Upload files and track failures
ANY_FAILED=0

for FILE in "${XML_FILES[@]}"; do
  # Extract filename without extension for 'typ'
  BASENAME="$(basename "$FILE" .xml)"
  echo "Uploading $FILE (typ=$BASENAME)..."

  if ! curl --max-time 120 --connect-timeout 10 --fail-with-body \
    -X POST "$UPLOAD_URL" \
    -F "branch=${BRANCH}" \
    -F "revision=${REVISION}" \
    -F "platform=${PLATFORM}" \
    -F "bbnum=${BBNUM}" \
    -F "typ=${BASENAME}" \
    -F "file=@${FILE};type=application/xml"; then
      echo "Upload failed for $FILE"
      ANY_FAILED=1
  else
    echo "Upload succeeded for $FILE"
  fi
done

# Step 5: Final result
if [[ $ANY_FAILED -ne 0 ]]; then
  echo "One or more uploads failed."
  exit 1
else
  echo "All uploads succeeded."
  exit 0
fi
