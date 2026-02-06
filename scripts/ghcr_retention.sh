#!/usr/bin/env bash
set -euo pipefail


ORG="${ORG:-}" # Leave empty for using user's API scope.
USER="${USER:-}"
PACKAGE="${PACKAGE:-buildbot/bb-worker}"    # may include '/'
RETENTION_MONTHS="${RETENTION_MONTHS:-6}"
TAG_PREFIX="${TAG_PREFIX:-hist_}"
PACKAGE_ESCAPED="${PACKAGE//\//%2F}"

# API scope
if [ -n "$ORG" ]; then
  SCOPE_PATH="/orgs/$ORG"
  OWNER_LABEL="org:$ORG"
else
  SCOPE_PATH="/users/$USER"
  OWNER_LABEL="user:$USER"
fi

cutoff="$(date -u -d "${RETENTION_MONTHS} months ago" +%Y-%m-%dT%H:%M:%SZ)"

echo "Owner: $OWNER_LABEL"
echo "Package: $PACKAGE"
echo "Retention (months): $RETENTION_MONTHS"
echo "Tag prefix: $TAG_PREFIX"
echo "Cutoff: $cutoff"
echo

IDS="$(
  gh api "${SCOPE_PATH}/packages/container/${PACKAGE_ESCAPED}/versions" --paginate \
  | jq -c --arg cutoff "$cutoff" --arg prefix "$TAG_PREFIX" '
      .[]
      | select((.metadata.container.tags // []) | length == 1)
      | select((.metadata.container.tags[0] | startswith($prefix)))
      | select((.updated_at | fromdateiso8601) <= ($cutoff | fromdateiso8601))
      | {id, updated_at, tags: (.metadata.container.tags // [])}
    '
)"

if [ -z "$IDS" ]; then
  echo "No package versions eligible for deletion."
  exit 0
fi

echo "Objects to delete: $(echo "$IDS" | jq -s 'length')"
echo "The following package versions are eligible for deletion:"
echo "$IDS" | jq -s '.'
echo

echo "$IDS" | jq -r '.id' | while read -r id; do
  [ -z "$id" ] && continue
  echo "Deleting version: $id"
  gh api -X DELETE "${SCOPE_PATH}/packages/container/${PACKAGE_ESCAPED}/versions/$id"
done
