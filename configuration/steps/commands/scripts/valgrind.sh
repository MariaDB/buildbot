#!/usr/bin/env bash

failed=0
success_tests=()
failed_tests=()
programs=()

if [ "$#" -eq 0 ]; then
  echo "Usage: $0 <program-or-glob> [program-or-glob ...]" >&2
  exit 2
fi

for arg in "$@"; do
  if [[ "$arg" == *'*'* || "$arg" == *'?'* || "$arg" == *'['* ]]; then
    while IFS= read -r match; do
      programs+=("$match")
    done < <(compgen -G "$arg")
  else
    programs+=("$arg")
  fi
done

if [ "${#programs[@]}" -eq 0 ]; then
  echo "No programs matched." >&2
  exit 2
fi

for prog in "${programs[@]}"; do
  if [ ! -e "$prog" ]; then
    echo "WARNING: not found: $prog" >&2
    continue
  fi

  if [ ! -x "$prog" ]; then
    echo "WARNING: not executable: $prog" >&2
    continue
  fi

  name="$(basename "$prog")"
  log="valgrind-${name}.log"

  echo "VALGRIND_BEGIN::$prog::log=$log"

  valgrind \
    --leak-check=full \
    --show-leak-kinds=all \
    --error-limit=no \
    "$prog" \
    2> >(tee "$log" >&2) || true

  definite=$(awk '/definitely lost:/ {print $4}' "$log" | tail -1 | tr -d ',')
  indirect=$(awk '/indirectly lost:/ {print $4}' "$log" | tail -1 | tr -d ',')
  possible=$(awk '/possibly lost:/ {print $4}' "$log" | tail -1 | tr -d ',')

  definite=${definite:-0}
  indirect=${indirect:-0}
  possible=${possible:-0}

  if [ "$definite" -ne 0 ] || [ "$indirect" -ne 0 ] || [ "$possible" -ne 0 ]; then
    failed=1
    failed_tests+=("$prog :: definite=$definite indirect=$indirect possible=$possible")
    echo "VALGRIND_FAILURE::$prog::definite=$definite::indirect=$indirect::possible=$possible"
  else
    success_tests+=("$prog :: no definite/indirect/possible leaks")
    echo "VALGRIND_SUCCESS::$prog"
  fi
done

echo
echo "================ VALGRIND FINAL SUMMARY ================"
echo "Successful programs:"
if [ "${#success_tests[@]}" -gt 0 ]; then
  printf "%s\n" "${success_tests[@]}"
else
  echo "(none)"
fi

echo
echo "Failed programs:"
if [ "${#failed_tests[@]}" -gt 0 ]; then
  printf "%s\n" "${failed_tests[@]}"
else
  echo "(none)"
fi
echo "========================================================"

exit "$failed"