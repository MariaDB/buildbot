#!/usr/bin/env bash

set -xeuvo pipefail

tarbuildnum=${1}
mariadb_version=${2}
mariadb_version=${mariadb_version#*-}
buildername=${3:-amd64-ubuntu-2004-deb-autobake}
master_branch=${mariadb_version%\.*}
#commit=${4:-0}
branch=${5:-${master_branch}}
prod_environment=${6:-True}

rm -f last_tag

# keep in sync with docker-cleanup script
if [[ $branch = *pkgtest* ]]; then
  container_tag=${branch#bb-}
elif [[ $branch =~ ^preview ]]; then
  container_tag=${branch#preview-}
else
  container_tag=$master_branch
fi

ubi=
if [[ "$buildername" = *-rhel-9-rpm-autobake ]]; then
    ubi=-ubi
    master_branch=${master_branch}-ubi
fi

# Container tags must be lower case.
container_tag=${container_tag,,*}${ubi}

image=mariadb-${tarbuildnum}${ubi}

# keep a count of architectures that have reached this step
# and only build once they are all here.

if ! buildah manifest exists "$image"; then
	echo "No manifest we can't push"
	# Not fatal, but this means logic can stay
	# here rather than in bb steps.
	exit 0
fi

#
# Dev manifest is already made
#

devmanifest=$image


#
# PUSHIT - if the manifest if complete, i.e. all supported arches are there, we push
#
if [ -n "$ubi" ]; then
  arches=( linux/amd64 )
else
  arches=( linux/amd64 linux/arm64/v8 linux/ppc64le linux/s390x )
fi

manifest_image_cleanup() {
  local manifest=$1
  buildah manifest rm "$manifest" || echo "already removed"

  for arch in "${arches[@]}"; do
    # -f will remove all tags of same, like wordpress
    buildah rmi -f "${manifest}-${arch}" || echo "already gone"
  done
  buildah rmi --prune --force

  shift
  local t=$1
  rm -f "$t"
}

t=$(mktemp)

# Anything fails, like the API, cleanup
trap 'manifest_image_cleanup "$devmanifest" "$t"' EXIT

declare -A specialtags
if ! wget -nv https://downloads.mariadb.org/rest-api/mariadb/ -O "$t"; then
  echo >&2 "Wget failed"
fi
if [ "$branch" = 'main' ]; then
  specialtags['verylatest']=\"${container_tag}\"
else
  specialtags['verylatest']=$(jq '.major_releases[0].release_id' <"$t")
fi
specialtags['latest']=$(jq '.major_releases | map(select(.release_status == "Stable"))[0].release_id' <"$t")
specialtags['latest-lts']=$(jq '.major_releases | map(select(.release_status == "Stable" and .release_support_type == "Long Term Support"))[0].release_id' <"$t")
specialtags['earliest']=$(jq '.major_releases | map(select( (( (.release_eol_date // "2031-01-01") + "T00:00:00Z") | fromdate) > now))[-1].release_id' <"$t")
specialtags['earliest-lts']=$(jq '.major_releases | map(select(.release_status == "Stable" and .release_support_type == "Long Term Support" and (( (.release_eol_date // "2031-01-01") + "T00:00:00Z") | fromdate) > now ))[-1].release_id' <"$t")
for tag in "${!specialtags[@]}"; do
  if [ \""$container_tag"\" == "${specialtags[$tag]}" ]; then
    if [ "$prod_environment" = "True" ]; then
      buildah manifest push --all "$devmanifest" "docker://quay.io/mariadb-foundation/mariadb-devel:${tag}${ubi}"
    else
      echo "not pushing quay.io/mariadb-foundation/mariadb-devel:${tag}${ubi} as in DEV environment"
    fi
  fi
done
rm "$t"

buildah manifest inspect "$devmanifest" | tee "${t}"
trap 'manifest_image_cleanup "$devmanifest" "$t"' EXIT

if [ "$prod_environment" = "True" ]; then
  buildah manifest push --all "$devmanifest" "docker://quay.io/mariadb-foundation/mariadb-devel:${container_tag}"
fi
# Still want last_tag in dev environment to trigger wordpress build.
echo "${container_tag}" > last_tag

#
# MAKE Debug manifest

debugmanifest=${image}-debug

# --all-platforms incompatible with --build-arg
# https://github.com/containers/buildah/issues/5850
# buildah bud --all-platforms --jobs 4 --manifest "$debugmanifest" --build-arg BASE="$image" -f "mariadb-docker/Containerfile.debug$ubi"


# Temp disable this as it also wasn't functioning
manifest_image_cleanup "$devmanifest" "$t"
if false; then
## intentionally array to simple
# shellcheck disable=SC2124
archlist="${arches[@]}"
# comma separated
archlist=${archlist// /,}
buildah bud --platform "${archlist}" --jobs 4 --manifest "$debugmanifest" --build-arg BASE="$image" -f "mariadb-docker/Containerfile.debug$ubi"

# now $debugmanifest is build, we can cleanup $devmanifest
manifest_image_cleanup "$devmanifest" "$t"

buildah manifest inspect "$debugmanifest"

if [ "$prod_environment" = "True" ]; then
  buildah manifest push --all --rm "$debugmanifest" "docker://quay.io/mariadb-foundation/mariadb-debug:${container_tag}"
else
  buildah manifest rm "$debugmanifest"
fi

# end of broken debug container build
fi

# all untagged images removed, and any containers that might be running on them
buildah rmi --prune --force

# Delete old reference files
find . -name \*reference.txt  -type f -mtime +7 -delete

buildah images
# lost and forgotten (or just didn't make enough manifest items - build failure on an arch)
lastweek=$(date +%s --date='1 week ago')
# note - jq args are treated as strings and need to be cast tonumber to make the value comparable.

# clear buildah images
buildah images --json |
 jq --arg lastweek "$lastweek" '.[] | select(.created <= ( $lastweek | tonumber ) and any( .names[]? ; startswith("localhost/mariadb")) ) | .id' |
 xargs --no-run-if-empty buildah rmi --force || echo "had trouble removing buildah images"

# old ubuntu and base images that got updated so are Dangling
podman images --format=json |
  jq --arg lastweek "$lastweek" '.[] | select(.Created <= ( $lastweek | tonumber ) and .Dangling? ) | .Id' |
  xargs --no-run-if-empty podman rmi --force || echo "continuing cleanup anyway"

# clean buildah containers (nothing should be running)
buildah containers --format "{{.ContainerID}}" | xargs --no-run-if-empty buildah rm || echo "had trouble cleaning containers"

# clean images
buildah images --json |
  jq --arg lastweek "$lastweek" '.[] | select(.readonly ==false and .created <= ( $lastweek | tonumber ) and .names == null) | .id' |
  xargs --no-run-if-empty buildah rmi || echo "had trouble cleaning images"

# clean manifests
buildah images --json |
  jq --arg lastweek "$lastweek" '.[] | select(.readonly ==false and .created <= ( $lastweek | tonumber ) and ( try .names[0]? catch "" | startswith("localhost/mariadb-") )) | .id' |
  xargs --no-run-if-empty buildah manifest rm || echo "trouble cleaning manifests"

# what's left?
buildah images


trap - EXIT
