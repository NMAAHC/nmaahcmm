#!/usr/bin/env bash
# fixity.sh - make (default) or verify hash sidecars for TBM files.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${REPO_ROOT}/lib/common.sh"

tbm_trap_sigterm

if [[ -t 1 ]]; then
    BOLD=$'\033[1m'; BLUE=$'\033[34m'; CYAN=$'\033[36m'
    GREEN=$'\033[32m'; YELLOW=$'\033[33m'; DIM=$'\033[2m'; RESET=$'\033[0m'
else
    BOLD=''; BLUE=''; CYAN=''; GREEN=''; YELLOW=''; DIM=''; RESET=''
fi

SUPPORTED_ALGOS=(md5 sha1 sha256 sha512 crc32)

_usage() {
    cat <<EOF
${BOLD}${BLUE}USAGE:${RESET}
  ${GREEN}fixity.sh${RESET} ${CYAN}-i${RESET} ${YELLOW}PATH${RESET} [${YELLOW}PATH${RESET} ...] [options]

Run ${GREEN}fixity.sh${RESET} ${CYAN}-h${RESET} for detailed help.
EOF
}

_help() {
    cat <<EOF
${BOLD}${BLUE}NAME${RESET}
  ${GREEN}fixity.sh${RESET} — make or verify hash sidecars for files

${BOLD}${BLUE}USAGE${RESET}
  ${GREEN}fixity.sh${RESET} ${CYAN}-i${RESET} ${YELLOW}PATH${RESET} [${YELLOW}PATH${RESET} ...] [${CYAN}-a${RESET} ${YELLOW}ALGO${RESET}] [${CYAN}-p${RESET}] [${CYAN}-r${RESET}|${CYAN}-A${RESET}] [${CYAN}-n${RESET}]   ${DIM}# make (default)${RESET}
  ${GREEN}fixity.sh${RESET} ${CYAN}-i${RESET} ${YELLOW}PATH${RESET} [${YELLOW}PATH${RESET} ...] [${CYAN}-a${RESET} ${YELLOW}ALGO${RESET}] ${CYAN}--verify${RESET}            ${DIM}# verify${RESET}

${BOLD}${BLUE}OPTIONS${RESET}
  ${CYAN}-i${RESET}, ${CYAN}--input${RESET} ${YELLOW}PATH${RESET} [${YELLOW}PATH${RESET} ...]   One or more files or directories (directories are recursed)
  ${CYAN}-a${RESET}, ${CYAN}--algorithm${RESET} ${YELLOW}ALGO${RESET}          Hash algorithm: ${YELLOW}md5${RESET} (default), ${YELLOW}sha1${RESET}, ${YELLOW}sha256${RESET}, ${YELLOW}sha512${RESET}, ${YELLOW}crc32${RESET}
  ${CYAN}-c${RESET}, ${CYAN}--verify${RESET}                  Verify existing sidecars (auto-detects combined or per-file)
  ${CYAN}-p${RESET}, ${CYAN}--per-file${RESET}                Directory input: write a sidecar per source file
  ${CYAN}-r${RESET}, ${CYAN}--relative${RESET}                Combined mode: relative paths in the manifest (default)
  ${CYAN}-A${RESET}, ${CYAN}--absolute${RESET}                Combined mode: absolute paths in the manifest
  ${CYAN}-n${RESET}, ${CYAN}--dry-run${RESET}                 Print planned actions, write nothing
  ${CYAN}-h${RESET}, ${CYAN}--help${RESET}                    Show this help

${BOLD}${BLUE}EXAMPLES${RESET}
  ${DIM}# MD5 sidecar for a single file${RESET}
  ${GREEN}fixity.sh${RESET} ${CYAN}-i${RESET} /Volumes/archive/<file>

  ${DIM}# MD5 sidecars for several files at once${RESET}
  ${GREEN}fixity.sh${RESET} ${CYAN}-i${RESET} a.mp3 b.mp3 c.mp3

  ${DIM}# One combined MD5 manifest for a directory (default)${RESET}
  ${GREEN}fixity.sh${RESET} ${CYAN}-i${RESET} /Volumes/archive/<dir>

  ${DIM}# Per-file SHA-256 sidecars inside a directory${RESET}
  ${GREEN}fixity.sh${RESET} ${CYAN}-i${RESET} /Volumes/archive/<dir> ${CYAN}-a${RESET} sha256 ${CYAN}-p${RESET}

  ${DIM}# Combined manifest with absolute paths${RESET}
  ${GREEN}fixity.sh${RESET} ${CYAN}-i${RESET} /Volumes/archive/<dir> ${CYAN}-A${RESET}

  ${DIM}# Verify (auto-detects combined or per-file)${RESET}
  ${GREEN}fixity.sh${RESET} ${CYAN}-i${RESET} /Volumes/archive/<dir> ${CYAN}--verify${RESET}

${BOLD}${BLUE}SIDECAR FORMAT${RESET}
  Per-file (single file or ${CYAN}-p${RESET}):
    One sidecar per source file: ${YELLOW}<file>.<algo>.txt${RESET}
    Single-line content: ${YELLOW}<hash>  <basename>${RESET}

  Combined (directory input, default):
    One manifest inside the directory: ${YELLOW}<dir>/<dirname>.<algo>.txt${RESET}
    One line per file: ${YELLOW}<hash>  <path>${RESET}
    Paths are relative to the input dir by default (${CYAN}-r${RESET}); absolute with ${CYAN}-A${RESET}.
EOF
}

_algo_valid() {
    local a
    for a in "${SUPPORTED_ALGOS[@]}"; do
        [[ "$1" == "$a" ]] && return 0
    done
    return 1
}

_hash_only() {
    local f="$1" algo="$2"
    case "$algo" in
        md5)
            if command -v md5sum >/dev/null 2>&1; then
                md5sum "$f" | awk '{print $1}'
            else
                md5 -q "$f"
            fi
            ;;
        sha1|sha256|sha512)
            local bits="${algo#sha}"
            if command -v "sha${bits}sum" >/dev/null 2>&1; then
                "sha${bits}sum" "$f" | awk '{print $1}'
            else
                shasum -a "$bits" "$f" | awk '{print $1}'
            fi
            ;;
        crc32)
            if command -v crc32 >/dev/null 2>&1; then
                crc32 "$f"
            else
                python3 - "$f" <<'PY'
import sys, zlib
c = 0
with open(sys.argv[1], "rb") as f:
    while True:
        d = f.read(1048576)
        if not d:
            break
        c = zlib.crc32(d, c)
print(f"{c:08x}")
PY
            fi
            ;;
        *)
            tbm_error "Unsupported algorithm: $algo"
            exit 2
            ;;
    esac
}

_iter_source_files() {
    local root="$1"
    if [[ -f "$root" ]]; then
        printf '%s\n' "$root"
    elif [[ -d "$root" ]]; then
        local args=(-type f) suf
        for suf in "${TBM_SIDECAR_SUFFIXES[@]}"; do
            args+=(! -name "*${suf}")
        done
        find "$root" "${args[@]}" | sort
    else
        tbm_error "Not a file or directory: $root"
        return 1
    fi
}

_entry_path() {
    local f="$1" root="$2" mode="$3"
    if [[ "$mode" == "absolute" ]]; then
        printf '%s\n' "$f"
    else
        printf '%s\n' "${f#${root}/}"
    fi
}

do_make_per_file() {
    local input="$1" algo="$2" dry="$3"
    local count=0 skipped=0 f sidecar hash file_list
    file_list="$(mktemp "${TMPDIR:-/tmp}/fixity.XXXXXX")" || { tbm_error "cannot create temp file"; return 1; }
    # List first and check the listing's exit status: a find error (e.g. an
    # unreadable subdirectory) must not let a partial run pass as success.
    if ! _iter_source_files "$input" > "$file_list"; then
        rm -f "$file_list"
        tbm_error "could not list all files under $input"
        return 1
    fi
    while IFS= read -r f; do
        sidecar="${f}.${algo}.txt"
        if [[ -f "$sidecar" ]]; then
            tbm_info "skip (sidecar exists): $f"
            skipped=$((skipped+1))
            continue
        fi
        if (( dry )); then
            tbm_info "[dry-run] would write: $sidecar"
        else
            if ! hash="$(_hash_only "$f" "$algo")"; then
                tbm_error "failed to hash: $f"
                rm -f "$file_list"
                return 1
            fi
            printf '%s  %s\n' "$hash" "$(basename "$f")" > "$sidecar"
            tbm_ok "wrote $sidecar"
        fi
        count=$((count+1))
    done < "$file_list"
    rm -f "$file_list"
    if (( count + skipped == 0 )); then
        tbm_error "no source files found in $input"
        return 1
    fi
    tbm_info "done: $count processed, $skipped skipped (algorithm: $algo, per-file)"
}

do_make_combined() {
    local input="$1" algo="$2" dry="$3" mode="$4"
    local name manifest tmp_manifest count=0 entry f hash file_list
    local lines=()
    name="$(basename "$input")"
    manifest="${input%/}/${name}.${algo}.txt"

    if [[ -f "$manifest" ]] && (( ! dry )); then
        tbm_warn "manifest exists, overwriting: $manifest"
    fi

    file_list="$(mktemp "${TMPDIR:-/tmp}/fixity.XXXXXX")" || { tbm_error "cannot create temp file"; return 1; }
    # List first and check the listing's exit status: a find error (e.g. an
    # unreadable subdirectory) must not let a partial manifest pass as complete.
    if ! _iter_source_files "$input" > "$file_list"; then
        rm -f "$file_list"
        tbm_error "could not list all files under $input"
        return 1
    fi
    while IFS= read -r f; do
        entry="$(_entry_path "$f" "$input" "$mode")"
        if (( dry )); then
            tbm_info "[dry-run] would hash: $entry"
        else
            if ! hash="$(_hash_only "$f" "$algo")"; then
                tbm_error "failed to hash: $f"
                rm -f "$file_list"
                return 1
            fi
            lines+=("${hash}  ${entry}")
            tbm_info "hashed: $entry"
        fi
        count=$((count+1))
    done < "$file_list"
    rm -f "$file_list"

    if (( count == 0 )); then
        tbm_error "no source files found in $input"
        return 1
    fi

    if (( dry )); then
        tbm_info "[dry-run] would write manifest: $manifest ($count entries)"
    else
        # mktemp creates the file exclusively, so a stale temp or pre-planted
        # symlink can't redirect the write; the rename replaces the manifest
        # only after every hash has succeeded. mktemp files are 0600, so
        # restore what a plain umask-honoring write would have produced.
        tmp_manifest="$(mktemp "${manifest}.XXXXXX")" || { tbm_error "cannot create temp manifest"; return 1; }
        printf '%s\n' "${lines[@]}" > "$tmp_manifest"
        chmod "$(printf '%o' $(( 0666 & ~0$(umask) )))" "$tmp_manifest"
        mv "$tmp_manifest" "$manifest"
        tbm_ok "wrote $manifest ($count entries, path-mode: $mode)"
    fi
}

do_verify_per_file() {
    local input="$1" algo="$2"
    local ok=0 failed=0 missing=0 f sidecar expected actual file_list
    file_list="$(mktemp "${TMPDIR:-/tmp}/fixity.XXXXXX")" || { tbm_error "cannot create temp file"; return 1; }
    if ! _iter_source_files "$input" > "$file_list"; then
        rm -f "$file_list"
        tbm_error "could not list all files under $input"
        return 1
    fi
    while IFS= read -r f; do
        sidecar="${f}.${algo}.txt"
        if [[ ! -f "$sidecar" ]]; then
            tbm_warn "no $algo sidecar: $f"
            missing=$((missing+1))
            continue
        fi
        expected="$(awk 'NR==1{print $1}' "$sidecar")"
        if ! actual="$(_hash_only "$f" "$algo")"; then
            tbm_error "MISMATCH: $f (cannot read file)"
            failed=$((failed+1))
            continue
        fi
        if [[ "$expected" == "$actual" ]]; then
            tbm_ok "match: $f"
            ok=$((ok+1))
        else
            tbm_error "MISMATCH: $f (expected $expected, got $actual)"
            failed=$((failed+1))
        fi
    done < "$file_list"
    rm -f "$file_list"
    tbm_info "verify: $ok ok, $failed failed, $missing missing (algorithm: $algo, per-file)"
    if (( ok + failed + missing == 0 )); then
        tbm_error "nothing to verify: no source files found in $input"
        return 1
    fi
    [[ $failed -eq 0 && $missing -eq 0 ]] || return 1
}

do_verify_combined() {
    local manifest="$1" input="$2" algo="$3"
    local ok=0 failed=0 missing=0 malformed=0 line hash entry file actual
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        if [[ "$line" != *"  "* ]]; then
            tbm_warn "malformed manifest line: $line"
            malformed=$((malformed+1))
            continue
        fi
        hash="${line%%  *}"
        entry="${line#*  }"
        if [[ "$entry" = /* ]]; then
            file="$entry"
        else
            file="${input%/}/${entry}"
        fi
        if [[ ! -f "$file" ]]; then
            tbm_warn "missing file: $file (entry: $entry)"
            missing=$((missing+1))
            continue
        fi
        if ! actual="$(_hash_only "$file" "$algo")"; then
            tbm_error "MISMATCH: $file (cannot read file)"
            failed=$((failed+1))
            continue
        fi
        if [[ "$hash" == "$actual" ]]; then
            tbm_ok "match: $file"
            ok=$((ok+1))
        else
            tbm_error "MISMATCH: $file (expected $hash, got $actual)"
            failed=$((failed+1))
        fi
    done < "$manifest"
    tbm_info "verify: $ok ok, $failed failed, $missing missing, $malformed malformed (algorithm: $algo, manifest: $manifest)"
    if (( ok + failed + missing + malformed == 0 )); then
        tbm_error "manifest has no entries: $manifest"
        return 1
    fi
    [[ $failed -eq 0 && $missing -eq 0 && $malformed -eq 0 ]] || return 1
}

do_verify_auto() {
    local input="$1" algo="$2"
    if [[ -f "$input" ]]; then
        do_verify_per_file "$input" "$algo"
        return
    fi
    local name manifest
    name="$(basename "$input")"
    manifest="${input%/}/${name}.${algo}.txt"
    if [[ -f "$manifest" ]]; then
        do_verify_combined "$manifest" "$input" "$algo"
    else
        tbm_info "no combined manifest found, falling back to per-file"
        do_verify_per_file "$input" "$algo"
    fi
}

main() {
    if [[ $# -eq 0 ]]; then _usage; exit 0; fi
    local inputs=() algo="md5" dry=0 verify=0 per_file=0 rel=0 abs=0 flag=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -i|--input)
                flag="$1"
                shift
                if [[ $# -eq 0 || "$1" == -* ]]; then
                    tbm_error "${flag} requires at least one PATH"; _usage >&2; exit 2
                fi
                while [[ $# -gt 0 && "$1" != -* ]]; do
                    inputs+=("$1"); shift
                done
                ;;
            -a|--algorithm)
                [[ $# -ge 2 ]] || { tbm_error "$1 requires an ALGO argument"; _usage >&2; exit 2; }
                algo="$2"; shift 2 ;;
            -c|--verify) verify=1; shift ;;
            -n|--dry-run) dry=1; shift ;;
            -p|--per-file) per_file=1; shift ;;
            -r|--relative) rel=1; shift ;;
            -A|--absolute) abs=1; shift ;;
            -h|--help) _help; exit 0 ;;
            *) tbm_error "Unknown arg: $1"; _usage >&2; exit 2 ;;
        esac
    done
    (( ${#inputs[@]} > 0 )) || { tbm_error "-i PATH required"; _usage >&2; exit 2; }
    _algo_valid "$algo" || { tbm_error "Unsupported algorithm: $algo (supported: ${SUPPORTED_ALGOS[*]})"; exit 2; }
    (( rel && abs )) && { tbm_error "--relative and --absolute are mutually exclusive"; exit 2; }
    (( per_file && (rel || abs) )) && { tbm_error "--relative/--absolute don't apply to --per-file mode"; exit 2; }
    (( verify && dry )) && { tbm_error "--dry-run is not valid with --verify"; exit 2; }

    # Validate every input up front so a bad path can't abort a half-finished run.
    local input
    for input in "${inputs[@]}"; do
        if [[ ! -f "$input" && ! -d "$input" ]]; then
            tbm_error "Not a file or directory: $input"
            exit 2
        fi
        if [[ -f "$input" ]] && (( rel || abs )); then
            tbm_error "--relative/--absolute only apply to directory input: $input"
            exit 2
        fi
    done

    local status=0
    for input in "${inputs[@]}"; do
        if [[ -d "$input" ]]; then
            input="$(cd "$input" && pwd -P)"
        fi
        if (( verify )); then
            do_verify_auto "$input" "$algo" || status=1
        elif [[ -f "$input" ]] || (( per_file )); then
            do_make_per_file "$input" "$algo" "$dry" || status=1
        else
            local mode="relative"
            (( abs )) && mode="absolute"
            do_make_combined "$input" "$algo" "$dry" "$mode" || status=1
        fi
    done
    exit "$status"
}

main "$@"
