#!/bin/bash

# Configuration
DIR_CI=$1                                 # Directory containing CI built rpms
DIR_REBUILT=$2                            # Directory containing rebuilt rpms
EXCLUDE_RPMS=$3                           # Comma-separated list of patterns to exclude from comparison
EXCLUDE_PATTERNS=("${EXCLUDE_RPMS//,/ }") # Convert to array
REQUIRES_DIR="rpm_requires"               # Directory to store rpm requires output

# === Function: Validate directory existence and non-empty (simple ls check) ===
validate_directory() {
    local DIR="$1"
    if [ ! -d "$DIR" ]; then
        echo "Error: Directory '$DIR' does not exist."
        exit 1
    fi

    if [ -z "$(ls -A "$DIR" 2>/dev/null)" ]; then
        echo "Error: Directory '$DIR' is empty."
        exit 1
    fi
}

# === Function: Get filtered file list (with exclusions) ===
get_filtered_file_list() {
    local DIR="$1"
    local FIND_CMD=(find "$DIR" -maxdepth 1 -type f)

    for PATTERN in "${EXCLUDE_PATTERNS[@]}"; do
        FIND_CMD+=(! -name "$PATTERN")
    done

    "${FIND_CMD[@]}" | xargs -r -n1 basename | sort
}

# === Function: Run rpm requires on each file in both directories and save outputs ===
run_rpm_requires() {
    local FILES="$1"  # multiline string of filenames
    mkdir -p "$REQUIRES_DIR/CI"
    mkdir -p "$REQUIRES_DIR/REBUILT"

    echo "Running rpm requires queries..."

    while IFS= read -r FILENAME; do
        local FILEPATH_CI="$DIR_CI/$FILENAME"
        local FILEPATH_REBUILT="$DIR_REBUILT/$FILENAME"
        rpm -q --requires -p "$FILEPATH_CI" 2>/dev/null | sed -e 's/>=.*/>=/' -e 's/\([A-Z0-9._]*\)\([0-9]*bit\)$//' -e '/MariaDB-compat/d' -e '/rpmlib(FileCaps)/d' > "$REQUIRES_DIR/CI/$FILENAME.requires"
        rpm -q --requires -p "$FILEPATH_REBUILT" 2>/dev/null | sed -e 's/>=.*/>=/' -e 's/\([A-Z0-9._]*\)\([0-9]*bit\)$//' -e '/MariaDB-compat/d' -e '/rpmlib(FileCaps)/d' > "$REQUIRES_DIR/REBUILT/$FILENAME.requires"
    done <<< "$FILES"
}

# === Function: Compare rpm requires output files and report differences ===
compare_requires() {
    local DIFFS_FOUND=0
    echo "Comparing rpm requires files..."

    for REQFILE_CI in "$REQUIRES_DIR/CI/"*.requires; do
        FILENAME=$(basename "$REQFILE_CI" .requires)
        REQFILE_REBUILT="$REQUIRES_DIR/REBUILT/$FILENAME.requires"

        if [ ! -f "$REQFILE_REBUILT" ]; then
            echo "File '$FILENAME' missing in REBUILT requires output."
            DIFFS_FOUND=1
            continue
        fi

        # Compare ignoring order and whitespace by sorting lines before diff
        if ! diff -q <(sort "$REQFILE_CI") <(sort "$REQFILE_REBUILT") >/dev/null; then
            echo "=================================================================="
            echo "Difference found in requires for '$FILENAME':"
            echo "=================================================================="
            diff -u <(sort "$REQFILE_CI") <(sort "$REQFILE_REBUILT")
            DIFFS_FOUND=1
        fi
    done

    if [ $DIFFS_FOUND -eq 0 ]; then
        echo "All rpm requires outputs match."
    else
        echo "Some differences detected in rpm requires outputs."
        exit 1
    fi
}

# === Main script execution ===

validate_directory "$DIR_CI"
validate_directory "$DIR_REBUILT"

FILES_CI=$(get_filtered_file_list "$DIR_CI")
FILES_REBUILT=$(get_filtered_file_list "$DIR_REBUILT")

ONLY_IN_CI=$(comm -23 <(echo "$FILES_CI") <(echo "$FILES_REBUILT"))
ONLY_IN_REBUILT=$(comm -13 <(echo "$FILES_CI") <(echo "$FILES_REBUILT"))

if [ -n "$ONLY_IN_CI" ] || [ -n "$ONLY_IN_REBUILT" ]; then
    echo "Error: File name mismatch detected between directories."
    if [ -n "$ONLY_IN_CI" ]; then
        echo "Files only in CI ($DIR_CI):"
        echo "$ONLY_IN_CI"
    fi
    if [ -n "$ONLY_IN_REBUILT" ]; then
        echo "Files only in REBUILT ($DIR_REBUILT):"
        echo "$ONLY_IN_REBUILT"
    fi
    exit 1
else
    echo "Success: Files match by name. Continuing processing..."
    echo "$FILES_CI" > rpms_to_compare.txt
    # Run rpm requires queries and save outputs with filtering
    run_rpm_requires "$FILES_CI"
    # Compare rpm requires outputs
    compare_requires
fi