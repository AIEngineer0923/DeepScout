#!/usr/bin/env bash
# DeepScout repository hygiene scan (secrets, credentials, local paths).
set -euo pipefail

ROOT="${1:-.}"
cd "$ROOT"

echo "[scan-secrets] Scanning: $(pwd)"

block=0

scan_tree() {
  if [ -d .git ]; then
    git ls-files
  else
    find . -type f \
      -not -path './.git/*' \
      -not -path './.env' \
      -not -path './.env.*'
  fi
}

while IFS= read -r f; do
  [ -f "$f" ] || continue
  case "$f" in
    .env|.env.*) continue ;;
    scripts/scan-secrets.sh) continue ;;
  esac

  if grep -Eq 'AKIA[0-9A-Z]{16}' "$f" 2>/dev/null; then
    echo "BLOCK: AWS access key pattern in $f"
    block=1
  fi
  if grep -Eq 'lsv2_[a-zA-Z0-9]{20,}' "$f" 2>/dev/null; then
    echo "BLOCK: credential pattern in $f"
    block=1
  fi
  if grep -Eq 'sk-ant-[a-zA-Z0-9-]{20,}' "$f" 2>/dev/null; then
    echo "BLOCK: credential pattern in $f"
    block=1
  fi
  if grep -Eq 'sk-[a-zA-Z0-9]{20,}' "$f" 2>/dev/null; then
    echo "BLOCK: credential pattern in $f"
    block=1
  fi
  if grep -Eq 'AIza[0-9A-Za-z_-]{20,}' "$f" 2>/dev/null; then
    echo "BLOCK: Google API key pattern in $f"
    block=1
  fi
  if grep -Eq 'Co-authored-by: Cursor' "$f" 2>/dev/null; then
    echo "BLOCK: Cursor attribution in $f"
    block=1
  fi
  if grep -Eq '/Users/[^/]+/' "$f" 2>/dev/null; then
    echo "BLOCK: local absolute path in $f"
    block=1
  fi
done < <(scan_tree)

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if git ls-files --error-unmatch .env >/dev/null 2>&1; then
    echo "BLOCK: .env is tracked by git"
    block=1
  fi
fi

if [ "$block" -eq 1 ]; then
  echo "[scan-secrets] FAIL"
  exit 1
fi

echo "[scan-secrets] OK"
exit 0
