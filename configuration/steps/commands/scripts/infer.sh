#!/bin/bash

# Infer script for performing
# static analysis on the MariaDB codebase

set -x -e

infer --version

if [ $# -lt 1 ]; then
	echo insufficient args >&2
	exit 1
fi

# Testing this version
branch=$1
repository=${2:-"https://github.com/MariaDB/server.git"}
environment=${3:-"PROD"}

if [ -z "$branch" ]; then
  echo "usage $0 {branch/commit}" >&2
  exit 1
fi

trap "cleanup_for_CI" EXIT

################################################################################
##                               CONFIGURATION                                ##
################################################################################

base=$PWD
result_dir=$PWD/infer_results
infer="/mnt/infer/$environment"
sources="/mnt/src/$environment/server"
# less than zabbix (80) warning.
max_usage=75 # maximum disk usage (in percent)
limit=50 # number of commits away to consider for a differential build/analysis
: "${JOBS:=4}"

################################################################################
##                               FUNCTIONS                                    ##
################################################################################

create_dirs()
{
  mkdir -p "$infer"
  mkdir -p "$sources"
}

# Inputs: $branch
# Postconditions:
# * $sources is checked out to $branch
# * $commit set to the reference
get_source()
{
  pushd "$sources"
  trap 'popd' RETURN
  if [ ! -d .git ]; then
    git clone "$repository" .
  else
    git clean -df
  fi
  git config --global advice.detachedHead false
  git fetch origin "$branch"
  git checkout -f FETCH_HEAD
  git submodule update --init --recursive --jobs "${JOBS}"
  git clean -df
  commit=$(git rev-parse FETCH_HEAD)
}


cleanup_for_CI()
{
  rm -rf "${result_dir}"/*.db "${result_dir}"/tmp
}

# Function to get current disk usage (integer percent)
get_usage() {
    df -P "$infer" | awk 'NR==2 {gsub(/%/,""); print $5}'
}

host_cleanup()
{
  rm -rf "${result_dir}" index.txt report.json
  echo "Checking disk usage on $(df -h "$infer" | tail -n -1)"
  usage=$(get_usage)
  echo "Current usage: ${usage}%"

  # Find directories sorted by oldest modification time (oldest first)
  mapfile -t dirs < <(
    find "$infer" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' \
    | sort -n | awk '{print $2}'
  )

  # Loop through and delete until below threshold
  for dir in "${dirs[@]}"; do
      if (( usage < max_usage )); then
          echo "Disk usage is ${usage}%, below ${max_usage}%. Done."
          break
      fi

      echo "Deleting oldest directory: $dir"
      rm -rf -- "$dir"

      usage=$(get_usage)
      echo "New usage: ${usage}%"
  done

  if (( usage >= max_usage )); then
      echo "Warning: disk still above ${max_usage}% after deleting all directories!"
  else
      echo "Done. Disk usage now ${usage}%."
  fi
}

# Precondition: get_sources
# Returns:
#  0 - full scan needed
#  1 - incremental scan
# Postcondition for return 0
#
# Postcondition for return 1
# * $base/index.txt - list of file differences
# * $merge_base - the reference commit
# * $result_dir - is copy of the results from the $merge_base
# * $infer/$merge_base - is touched - (recently used marker)
populate_differences()
{
  pushd "$sources"
  trap 'popd' RETURN

  # Just assume we diverged from main at some point
  # Using $commit because merge-base didn't process
  # pull request references.
  merge_base=$(git merge-base "$commit" origin/main)

  # Find something closer - e.g. we've appended to a branch
  # we've already tested
  mapfile -t commits < <(git rev-list "${merge_base}..FETCH_HEAD")
  for common_commit in "${commits[@]}"; do
    if [ -d "${infer}/$common_commit" ]; then
      break;
    fi
  done
  if [ ! -d "${infer}/$common_commit" ]; then
    return 1
  fi
  merge_base=$common_commit
  # The file changes we from last results
  git diff --name-only FETCH_HEAD.."${merge_base}" | tee "$base"/index.txt

  if [ ! -s "$base"/index.txt ]; then
    echo "Empty changes - nothing necessary"
    rm "$base"/index.txt
    exit 0
  fi

  if [ "$(wc -l < "${base}"/index.txt)" -gt $limit ]; then
    echo "More than $limit changes, just do a full generation"
    rm "$base/index.txt"
    return 1
  fi

  # use previous results as a base
  cp -a "$infer/$merge_base" "$result_dir"

  # Using as a recently used maker
  # Eventually we can remove/clear based on not being looked at
  touch "$infer/$merge_base"
  return 0
}

# Builds compiler commands database (compile_commands.json) for infer
# and generated source file that infer will need to scan
build()
{
  cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
        -DCMAKE_C_COMPILER=clang \
        -DCMAKE_CXX_COMPILER=clang++ \
        -S "${sources}" -B "${base}"/bld
  cmake --build "${base}"/bld \
        --target GenError GenServerSource GenUnicodeDataSource GenFixPrivs \
        --parallel "$JOBS"
}

infer_cmd()
{
  if [ -f "${sources}"/.infer/config ]; then
    infer --inferconfig-path "${@}"
  else
    infer "${@}"
  fi
}

capture()
{
  infer_cmd capture --compilation-database compile_commands.json --project-root "${sources}" --results-dir "${result_dir}" "$@"
}

analyze()
{
  analyze_cmd=(analyze --project-root "${sources}" --results-dir "${result_dir}" --max-jobs "${JOBS}" "$@")
  if [ -f "$sources"/.infer/report-block-list.spec.json ]; then
    # fp reports
    analyze_cmd+=( --report-block-list-spec="${sources}"/.infer/report-block-list-spec.json )
  fi
  infer_cmd "${analyze_cmd[@]}"
}


full_analysis()
{
  pushd "$base"/bld
  trap 'popd' RETURN
  echo "full run, this could take a while"
  capture
  analyze
  cp -a "$result_dir" "$infer/$commit"
}

incremental_analysis()
{
  pushd "$base"/bld
  trap 'popd' RETURN

  echo "incremental run"
  # We've copied over a result dir, so we're continuing
  # https://fbinfer.com/docs/infer-workflow/#differential-workflow
 # using 'infer capture" instead infer run
  capture --reactive

  # some form of incremental
  analyze --changed-files-index "$base"/index.txt

  # Preserve result
  cp "${result_dir}"/report.json "$base"/report.json

  # just in case these have changed, including generated files
  build

  # Can we use the previous captured $infer/$merge_base
  capture --merge-capture "$infer/$merge_base" --reactive --mark-unchanged-procs

  analyze --incremental-analysis  --changed-files-index ../index.txt

  # It may be merged next, or a commit pushed on top of it.
  infer_cmd reportdiff --report-current "$base"/report.json --report-previous "${result_dir}"/report.json  --project-root "${sources}" --results-dir "${result_dir}"
  ## At this point we have infer_results/differential/{fixed,introduced}.json
  #!? Change the name as we're going to use differential as a main branch difference
  #!!mv "${result_dir}"/differential "${result_dir}"/diff_prev_commit

  rm -rf "$base"/bld "$base"/index.txt

  # Useful enough to save as $infer/
  # Its unknown if this is on main branch or now, but just save.
  # If its merged next, then a commit exists, if a user appends
  # a commit, we've got a smaller delta.
  cp -a "${result_dir}" "$infer/${commit}"
}

check()
{
  file=$1
  msg=$2
  if [ -f "${file}" ]; then
    filesize=$(stat -c%s "$file")
    # 2 is the size of an empty json array '[]'
    if [ "$filesize" -gt 2 ]; then
      echo "$msg"
      echo
      echo "See below step for the location to the ${file} contents"
      return 1
    fi
  fi
  return 0
}

differential_to_main_branch()
{
  # Look at the changes from the main branch
  #
  # Take the main branch report.json
  # remove fixed, add introduced, and then walk
  # though other commits, if they exist, and apply the
  # same again up until, and including the last commit
  source "$sources"/VERSION
  branch=${MYSQL_VERSION_MAJOR}.${MYSQL_VERSION_MINOR}

  pushd "$sources"
  merge_base=$(git merge-base "origin/$branch" "$commit")
  #mapfile -t commits < <(git rev-list "${merge_base}..${commit}")
  popd

  ref_base=$infer/$merge_base/report.json
  # .hash isn't unique, even when combined with .node_key.
  # If there are multiple instances of the same failure in the same function in
  # a file duplicates result.
  #for common_commit in "${commits[@]}"; do
  #  diff_dir="${infer}/$common_commit"/differential/
  #  if [ -d "$diff_dir" ]; then
  #    # removed fixed issues and append introduced.
  #    jq --slurpfile to_remove  "${diff_dir}"/fixed.json '
  #      ($to_remove[0] | map(.hash)) as $hashes_to_remove
  #      | map(select(.hash as $h | $hashes_to_remove | index($h) | not))' \
  #      "${ref_base}" > "${base}"/filtered.json
  #    ref_base=/tmp/report.json
  #    jq -s 'add | unique_by(.hash)' "${base}"/filtered.json  "${diff_dir}"/introduced.json > "${ref_base}"
  #  fi
  #done
  #rm -f "${base}"/filtered.json

  infer_cmd reportdiff --report-current "${base}/report.json" --report-previous "${ref_base}" --project-root "${sources}" --results-dir "${result_dir}_diff"

  result_dir_main_diff=${result_dir}/main_diff
  mv "${result_dir}_diff"/differential/ "${result_dir_main_diff}"

  if [ "$RUN_MODE" = "incremental" ]; then
    check "${result_dir}"/differential/fixed.json "Good human! Thanks for fixing the bad things in the last commit"
    check "${result_dir}"/differential/introduced.json "Bad human! Don't introduce bad things in the last commit" >&2
  fi

  # A increment run would compute to fixing everything not analyzed.
  check "${result_dir_main_diff}"/fixed.json "Good human! Thanks for fixing the bad things"
  if ! check "${result_dir_main_diff}"/introduced.json "Bad human! Don't introduce bad things" >&2; then
    exit 1
  fi
}

################################################################################
##                               MAIN SCRIPT                                  ##
################################################################################

create_dirs
host_cleanup

get_source

if [ -d "${infer}/$commit" ]; then
  echo "Already scanned $commit"
  exit 0
fi

if ! populate_differences; then
  echo "No common commit ancestor with analysis or over depth limit($limit)" >&2
  echo "This is going to take a while for a full scan"
fi

if [ ! -f index.txt ]; then
  RUN_MODE="full"
else
  RUN_MODE="incremental"
fi

build

if [ "$RUN_MODE" = "full" ]; then
  full_analysis
  cp "$result_dir"/report.json "${base}"
fi
if [ "$RUN_MODE" = "incremental" ]; then
  incremental_analysis
fi

rm -rf "$base"/bld

differential_to_main_branch
