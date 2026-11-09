#!/usr/bin/env bash
set -e
git config user.name "wp-job-radar"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add data/
if git diff --cached --quiet; then
  echo "no state change"
  exit 0
fi
git commit -q -m "state: $1 [skip ci]"
for i in 1 2 3 4 5; do
  if git pull -q --rebase && git push -q; then
    echo "state saved"
    exit 0
  fi
  sleep $((i * 4))
done
exit 1
