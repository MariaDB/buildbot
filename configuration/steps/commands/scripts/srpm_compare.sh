#!/bin/bash

set +x  # Disable tracing for the script

# Configuration
DIR_CI=$1                                 # Directory containing CI built rpms
DIR_REBUILT=$2                            # Directory containing rebuilt rpms
EXCLUDE_RPMS=$3                           # Comma-separated list of patterns to exclude from comparison
EXCLUDE_PATTERNS=("${EXCLUDE_RPMS//,/ }") # Convert to array
REQUIRES_DIR="rpm_requires"               # Directory to store rpm requires output
PACKAGE_CONTENT_DIR="package_content"     # Directory to store package content output

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

# === Function: Collect rpm requires or content ===
get_rpm_info() {
    local FILES="$1"
    local MODE="$2"

    if [ "$MODE" == "requires" ]; then
        mkdir -p "$REQUIRES_DIR/CI"
        mkdir -p "$REQUIRES_DIR/REBUILT"
    elif [ "$MODE" == "content" ]; then
        mkdir -p "$PACKAGE_CONTENT_DIR/CI"
        mkdir -p "$PACKAGE_CONTENT_DIR/REBUILT"
    else
        echo "Error: Invalid mode specified. Use 'requires' or 'content'."
        exit 1
    fi

    while IFS= read -r FILENAME; do
        local FILEPATH_CI="$DIR_CI/$FILENAME"
        local FILEPATH_REBUILT="$DIR_REBUILT/$FILENAME"

        if [ "$MODE" == "requires" ]; then
            rpm -q --requires -p "$FILEPATH_CI" 2>/dev/null | sed -e 's/>=.*/>=/' -e 's/\([A-Z0-9._]*\)\([0-9]*bit\)$//' -e '/MariaDB-compat/d' -e '/rpmlib(FileCaps)/d' > "$REQUIRES_DIR/CI/$FILENAME.requires"
            rpm -q --requires -p "$FILEPATH_REBUILT" 2>/dev/null | sed -e 's/>=.*/>=/' -e 's/\([A-Z0-9._]*\)\([0-9]*bit\)$//' -e '/MariaDB-compat/d' -e '/rpmlib(FileCaps)/d' > "$REQUIRES_DIR/REBUILT/$FILENAME.requires"
        elif [ "$MODE" == "content" ]; then
            # src_1 to src_0 replacement is to account for in-source (CI build) vs out-of-source (rebuild)
            # build-id paths are unique per build, so we exclude them
            rpm -qlp "$FILEPATH_CI" 2>/dev/null | sed -e '/\.build-id/d; s@/src_1@/src_0@' | sort -u > "$PACKAGE_CONTENT_DIR/CI/$FILENAME.content"
            rpm -qlp "$FILEPATH_REBUILT" 2>/dev/null | sed -e '/\.build-id/d; s@/src_1@/src_0@' | sort -u > "$PACKAGE_CONTENT_DIR/REBUILT/$FILENAME.content"
        fi
    done <<< "$FILES"
}


# === Function: Compare rpm requires or content ===
compare_rpm_info () {
    local MODE="$1"
    local DIR="$2"
    local OTHER_DIR="$3"

    touch "${MODE}_DIFFS.txt"
    for FILE in "$DIR"/*."$MODE"; do
        FILENAME=$(basename "$FILE" ".$MODE")
        OTHER_FILE="$OTHER_DIR/$FILENAME.$MODE"

        if ! diff -q <(sort "$FILE") <(sort "$OTHER_FILE") >/dev/null; then
            {
                msg="Difference found in rpm $MODE for '$FILENAME':"
                sep=$(printf '%*s' "${#msg}" '' | tr ' ' '=')
                echo "$sep"
                echo "$msg"
                echo "$sep"
                diff -u <(sort "$FILE") <(sort "$OTHER_FILE") || true
                EXIT_LATER=1
            } >> "${MODE}"_DIFFS.txt
        fi
    done
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
    EXIT_LATER=0
    echo "Success: Files match by name. Continuing processing..."
    echo "$FILES_CI" > rpms_to_compare.txt

    # Compare rpm requires
    get_rpm_info "$FILES_CI" "requires"
    compare_rpm_info "requires" "$REQUIRES_DIR/CI" "$REQUIRES_DIR/REBUILT"

    # Compare rpm content
    get_rpm_info "$FILES_CI" "content"
    compare_rpm_info "content" "$PACKAGE_CONTENT_DIR/CI" "$PACKAGE_CONTENT_DIR/REBUILT"

    if [ $EXIT_LATER -eq 1 ]; then
        cat requires_DIFFS.txt content_DIFFS.txt
        exit 1
    else
        echo "All checks passed successfully."
        exit 0
    fi
fi