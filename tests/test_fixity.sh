#!/usr/bin/env bash
# test_fixity.sh - integration tests for tools/fixity.sh and tools/fixity.py
#
# Usage: tests/test_fixity.sh
# Runs every test against both implementations, then a cross-implementation
# interop check. Exits 0 if everything passes, 1 otherwise.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PASS=0
FAIL=0
TOOL=""
LAST_OUT=""

WORK="$(mktemp -d "${TMPDIR:-/tmp}/fixity_test.XXXXXX")"
WORK="$(cd "$WORK" && pwd -P)"
trap 'rm -rf "$WORK"' EXIT

_label() { basename "$TOOL"; }
_pass() { PASS=$((PASS+1)); printf 'ok   [%s] %s\n' "$(_label)" "$1"; }
_fail() { FAIL=$((FAIL+1)); printf 'FAIL [%s] %s%s\n' "$(_label)" "$1" "${2:+ ($2)}"; }

# expect NAME EXPECTED_EXIT CMD... - run CMD, compare its exit status
expect() {
    local name="$1" want="$2" rc
    shift 2
    LAST_OUT="$("$@" 2>&1)"
    rc=$?
    if [[ "$rc" -eq "$want" ]]; then
        _pass "$name"
    else
        _fail "$name" "exit $rc, wanted $want"
        printf '%s\n' "$LAST_OUT" | sed 's/^/     | /'
    fi
}

# check NAME TEST-ARGS... - evaluate with test(1), e.g. check "x" -f /some/file
check() {
    local name="$1"
    shift
    if test "$@"; then _pass "$name"; else _fail "$name"; fi
}

fresh() { rm -rf "$WORK"; mkdir -p "$WORK"; }

run_suite() {
    ### per-file: multi-input make + verify round-trip
    fresh
    echo one > "$WORK/a.mp3"; echo two > "$WORK/b.mp3"; echo three > "$WORK/c.mp3"
    expect "multi-file make" 0 "$TOOL" -i "$WORK/a.mp3" "$WORK/b.mp3" "$WORK/c.mp3"
    check  "sidecars written" -f "$WORK/a.mp3.md5.txt" -a -f "$WORK/c.mp3.md5.txt"
    expect "multi-file verify" 0 "$TOOL" -i "$WORK/a.mp3" "$WORK/b.mp3" "$WORK/c.mp3" --verify

    ### hash mismatch fails, and later inputs are still verified
    echo corrupted >> "$WORK/b.mp3"
    expect "corrupt file fails verify" 1 "$TOOL" -i "$WORK/b.mp3" --verify
    expect "multi-input verify fails but continues" 1 "$TOOL" -i "$WORK/b.mp3" "$WORK/c.mp3" --verify
    case "$LAST_OUT" in
        *"match: ${WORK}/c.mp3"*) _pass "later input still verified after a failure" ;;
        *) _fail "later input still verified after a failure" ;;
    esac

    ### missing or empty sidecars fail verify
    fresh
    echo one > "$WORK/a.mp3"
    expect "missing sidecar fails verify" 1 "$TOOL" -i "$WORK/a.mp3" --verify
    : > "$WORK/a.mp3.md5.txt"
    expect "empty sidecar fails verify" 1 "$TOOL" -i "$WORK/a.mp3" --verify

    ### combined manifest: nested directories round-trip (relative paths)
    fresh
    mkdir -p "$WORK/pkg/sub"
    echo top > "$WORK/pkg/top.txt"
    echo deep > "$WORK/pkg/sub/deep.txt"
    expect "combined make on nested dir" 0 "$TOOL" -i "$WORK/pkg"
    if grep -q "  sub/deep.txt\$" "$WORK/pkg/pkg.md5.txt"; then
        _pass "manifest stores relative path for nested file"
    else
        _fail "manifest stores relative path for nested file" "$(cat "$WORK/pkg/pkg.md5.txt")"
    fi
    expect "combined verify on nested dir" 0 "$TOOL" -i "$WORK/pkg" --verify
    expect "per-file mode on nested dir" 0 "$TOOL" -i "$WORK/pkg" -p
    check  "nested per-file sidecar written" -f "$WORK/pkg/sub/deep.txt.md5.txt"

    ### duplicate basenames in different subdirs survive the round-trip
    fresh
    mkdir -p "$WORK/pkg/s1" "$WORK/pkg/s2"
    echo one > "$WORK/pkg/s1/take.wav"
    echo two > "$WORK/pkg/s2/take.wav"
    expect "duplicate basenames: make" 0 "$TOOL" -i "$WORK/pkg"
    expect "duplicate basenames: verify" 0 "$TOOL" -i "$WORK/pkg" --verify

    ### absolute path mode
    fresh
    mkdir -p "$WORK/pkg"
    echo x > "$WORK/pkg/x.txt"
    expect "absolute mode make" 0 "$TOOL" -i "$WORK/pkg" -A
    if grep -q "  ${WORK}/pkg/x.txt\$" "$WORK/pkg/pkg.md5.txt"; then
        _pass "manifest stores absolute path"
    else
        _fail "manifest stores absolute path" "$(cat "$WORK/pkg/pkg.md5.txt")"
    fi
    expect "absolute mode verify" 0 "$TOOL" -i "$WORK/pkg" --verify

    ### bad manifests fail verify
    fresh
    mkdir -p "$WORK/pkg"
    echo x > "$WORK/pkg/x.txt"; echo y > "$WORK/pkg/y.txt"
    "$TOOL" -i "$WORK/pkg" >/dev/null 2>&1
    rm "$WORK/pkg/y.txt"
    expect "manifest entry for deleted file fails verify" 1 "$TOOL" -i "$WORK/pkg" --verify
    echo y > "$WORK/pkg/y.txt"
    echo "deadbeef single-space-separator" >> "$WORK/pkg/pkg.md5.txt"
    expect "malformed manifest line fails verify" 1 "$TOOL" -i "$WORK/pkg" --verify
    : > "$WORK/pkg/pkg.md5.txt"
    expect "empty manifest fails verify" 1 "$TOOL" -i "$WORK/pkg" --verify

    ### a failed re-make must not destroy the existing manifest
    fresh
    mkdir -p "$WORK/pkg"
    echo x > "$WORK/pkg/x.txt"
    "$TOOL" -i "$WORK/pkg" >/dev/null 2>&1
    cp "$WORK/pkg/pkg.md5.txt" "$WORK/before.txt"
    echo y > "$WORK/pkg/unreadable.txt"
    chmod 000 "$WORK/pkg/unreadable.txt"
    if [[ "$(id -u)" -eq 0 ]]; then
        _pass "failed re-make keeps previous manifest (skipped: running as root)"
    else
        "$TOOL" -i "$WORK/pkg" >/dev/null 2>&1
        rc=$?
        if [[ $rc -ne 0 ]] && cmp -s "$WORK/before.txt" "$WORK/pkg/pkg.md5.txt"; then
            _pass "failed re-make keeps previous manifest intact"
        else
            _fail "failed re-make keeps previous manifest intact" "exit=$rc"
        fi
    fi
    chmod 644 "$WORK/pkg/unreadable.txt"

    ### argument handling
    fresh
    echo one > "$WORK/a.mp3"
    expect "nonexistent input exits 2" 2 "$TOOL" -i "$WORK/a.mp3" "$WORK/nope.mp3"
    check  "nothing written when any path is bad" ! -f "$WORK/a.mp3.md5.txt"
    expect "--input alias works" 0 "$TOOL" --input "$WORK/a.mp3"
    expect "sha256 make" 0 "$TOOL" -i "$WORK/a.mp3" -a sha256
    check  "sha256 sidecar written" -f "$WORK/a.mp3.sha256.txt"
    expect "sha256 verify" 0 "$TOOL" -i "$WORK/a.mp3" -a sha256 --verify
    expect "missing -i operand errors" 2 "$TOOL" -i
    expect "--relative and --absolute conflict" 2 "$TOOL" -i "$WORK" -r -A
    expect "--dry-run rejected with --verify" 2 "$TOOL" -i "$WORK" -c -n
}

for TOOL in "$REPO_ROOT/tools/fixity.sh" "$REPO_ROOT/tools/fixity.py"; do
    run_suite
done

### the two implementations must accept each other's output
TOOL="interop"
fresh
mkdir -p "$WORK/pkg/sub"
echo one > "$WORK/pkg/a.mp3"
echo two > "$WORK/pkg/sub/b.mp3"
"$REPO_ROOT/tools/fixity.sh" -i "$WORK/pkg" >/dev/null 2>&1
expect "py verifies sh manifest" 0 "$REPO_ROOT/tools/fixity.py" -i "$WORK/pkg" --verify
rm "$WORK/pkg/pkg.md5.txt"
"$REPO_ROOT/tools/fixity.py" -i "$WORK/pkg" >/dev/null 2>&1
expect "sh verifies py manifest" 0 "$REPO_ROOT/tools/fixity.sh" -i "$WORK/pkg" --verify

echo
echo "passed: $PASS, failed: $FAIL"
[[ $FAIL -eq 0 ]]
