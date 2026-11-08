#!/usr/bin/env bash
# Run every repository check that CI runs. Usage: .github/scripts/check-pool.sh [POOL_DIR]
#  1. check_fragment.py on every pool fragment at its viewBox width
#  2. scaffold_from_spec.py on every pool/*/spec.yaml, into a temp folder
#  3. build_gallery.py into a temp folder
#  4. check_look.py on every pool fragment (rendered in headless Chrome, dark theme);
#     skipped with a notice when no Chrome/Chromium is found (set CHROME=/path to force one)
#  5. python3 -m py_compile scripts/*.py
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
pool="${1:-$root/pool}"
py="${PYTHON:-python3}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
fail=0

echo "== check_fragment.py"
for dir in "$pool"/*/; do
  name="$(basename "$dir")"
  frag="$dir$name.html"
  [ -f "$frag" ] || { echo "skip $name/ (no $name.html)"; continue; }
  width="$("$py" - "$frag" <<'PY'
import re, sys
m = re.search(r'<svg\b[^>]*\bviewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)', open(sys.argv[1], encoding='utf-8').read())
print(int(float(m.group(1))) if m else 0)
PY
)"
  if [ "$width" = 0 ]; then echo "FAIL $name: no viewBox on the <svg>"; fail=1; continue; fi
  if "$py" "$root/scripts/check_fragment.py" "$frag" --name "$name" --rendered-width "$width"; then
    echo "ok   $name @ ${width}px"
  else
    echo "FAIL $name @ ${width}px"; fail=1
  fi
done

echo "== scaffold_from_spec.py"
for spec in "$pool"/*/spec.yaml; do
  [ -f "$spec" ] || continue
  name="$(basename "$(dirname "$spec")")"
  mkdir -p "$tmp/scaffold/$name"
  if "$py" "$root/scripts/scaffold_from_spec.py" "$spec" -o "$tmp/scaffold/$name/$name.html"; then
    echo "ok   $name"
  else
    echo "FAIL $name"; fail=1
  fi
done

echo "== build_gallery.py"
"$py" "$root/scripts/build_gallery.py" --pool "$pool" -o "$tmp/site" || fail=1

echo "== check_look.py"
for dir in "$pool"/*/; do
  name="$(basename "$dir")"
  frag="$dir$name.html"
  [ -f "$frag" ] || continue
  width="$(sed -n 's/.*<svg[^>]*viewBox="[-0-9. ]*[ ,][-0-9.]*[ ,]\([0-9.]*\)[ ,].*/\1/p' "$frag" | head -1)"
  [ -n "$width" ] || continue  # reported by the check_fragment.py step
  rc=0; out="$("$py" "$root/scripts/check_look.py" "$frag" --rendered-width "${width%.*}" 2>&1)" || rc=$?
  if [ "$rc" = 3 ]; then
    echo "notice: no Chrome/Chromium found, check_look.py skipped (set CHROME=/path/to/chrome)"; break
  elif [ "$rc" = 0 ]; then
    echo "ok   $name ($(echo "$out" | tail -1))"
  else
    echo "$out" | grep -E '^(FAIL|error)' || echo "$out" | tail -3
    echo "FAIL $name"; fail=1
  fi
done

echo "== py_compile"
"$py" -m py_compile "$root"/scripts/*.py && echo "ok" || fail=1

exit "$fail"
