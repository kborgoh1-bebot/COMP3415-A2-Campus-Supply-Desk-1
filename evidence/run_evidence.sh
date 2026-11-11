#!/bin/bash
# Usage: bash evidence/run_evidence.sh <baseline-ref> <refactored-ref> <cr01-ref> <final-ref>
# Checks out each commit, runs the full test suite, and saves the log to evidence/.
set -u
mkdir -p evidence
names=(1_baseline 2_after_refactoring 3_after_cr01 4_final)
refs=("$@"); start=$(git rev-parse --abbrev-ref HEAD)
for i in 0 1 2 3; do
  git checkout -q "${refs[$i]}" || exit 1
  { echo "# ${names[$i]} @ $(git log -1 --format='%h %s')"; echo "# $(date)";
    python -m unittest discover -s tests -v 2>&1; } > "/tmp/${names[$i]}.txt"
  echo "${names[$i]}: $(tail -1 /tmp/${names[$i]}.txt)"
done
git checkout -q "$start" && cp /tmp/{1,2,3,4}_*.txt evidence/
