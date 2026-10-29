#!/usr/bin/env bash
# package.sh - tidy a directory by moving metadata sidecars into a metadata/ subfolder.
# Everything else (source files, access copies, checksum sidecars) stays flat.

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

# Suffixes that move into metadata/. Everything else (sources, checksums,
# access copies) stays flat at the top level.
METADATA_SUFFIXES=(
    .mediainfo.txt .mediainfo.json .mediatrace.xml
    .ffprobe.json
    .exiftool.txt .exiftool.json
)

_usage() {
    cat <<EOF
${BOLD}${BLUE}USAGE:${RESET}
  ${GREEN}package.sh${RESET} ${CYAN}-i${RESET} ${YELLOW}DIR${RESET} [${CYAN}-n${RESET}] [${CYAN}--copy${RESET}]

Run ${GREEN}package.sh${RESET} ${CYAN}-h${RESET} for detailed help.
EOF
}

_help() {
    cat <<EOF
${BOLD}${BLUE}NAME${RESET}
  ${GREEN}package.sh${RESET} — tidy a directory by moving metadata sidecars into ${YELLOW}metadata/${RESET}

${BOLD}${BLUE}USAGE${RESET}
  ${GREEN}package.sh${RESET} ${CYAN}-i${RESET} ${YELLOW}DIR${RESET} [${CYAN}-n${RESET}] [${CYAN}--copy${RESET}]

${BOLD}${BLUE}OPTIONS${RESET}
  ${CYAN}-i${RESET} ${YELLOW}DIR${RESET}            Directory to tidy (in-place)
  ${CYAN}-n${RESET}, ${CYAN}--dry-run${RESET}      Print planned moves, don't touch anything
  ${CYAN}--copy${RESET}             Copy sidecars into ${YELLOW}metadata/${RESET} instead of moving
  ${CYAN}-h${RESET}, ${CYAN}--help${RESET}         Show this help

${BOLD}${BLUE}WHAT MOVES${RESET}
  These suffixes move into ${YELLOW}DIR/metadata/${RESET}:
    ${YELLOW}*.mediainfo.txt   *.mediainfo.json   *.mediatrace.xml${RESET}
    ${YELLOW}*.ffprobe.json${RESET}
    ${YELLOW}*.exiftool.txt    *.exiftool.json${RESET}

${BOLD}${BLUE}WHAT STAYS${RESET}
  Source files, checksum sidecars (${YELLOW}*.md5.txt${RESET}, ${YELLOW}*.sha256.txt${RESET}, ...) and access
  copies (${YELLOW}*_access.mp4${RESET}) stay flat at the top level.

${BOLD}${BLUE}SCOPE${RESET}
  Operates at the top level of ${YELLOW}DIR${RESET} only (no recursion). Running twice is
  safe — the second run just sees no sidecars left to move.

${BOLD}${BLUE}EXAMPLES${RESET}
  ${DIM}# Tidy a directory${RESET}
  ${GREEN}package.sh${RESET} ${CYAN}-i${RESET} /Volumes/archive/<dir>

  ${DIM}# Preview what would move${RESET}
  ${GREEN}package.sh${RESET} ${CYAN}-i${RESET} /Volumes/archive/<dir> ${CYAN}-n${RESET}

  ${DIM}# Copy instead of move (keep originals alongside)${RESET}
  ${GREEN}package.sh${RESET} ${CYAN}-i${RESET} /Volumes/archive/<dir> ${CYAN}--copy${RESET}
EOF
}

_find_metadata_sidecars() {
    local root="$1"
    local args=(-maxdepth 1 -type f \( )
    local first=1 suf
    for suf in "${METADATA_SUFFIXES[@]}"; do
        (( first )) || args+=(-o)
        args+=(-name "*${suf}")
        first=0
    done
    args+=(\))
    find "$root" "${args[@]}" 2>/dev/null | sort
}

main() {
    if [[ $# -eq 0 ]]; then _usage; exit 0; fi
    local input="" dry=0 copy=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -i) input="${2:-}"; shift 2 ;;
            -n|--dry-run) dry=1; shift ;;
            --copy) copy=1; shift ;;
            -h|--help) _help; exit 0 ;;
            *) tbm_error "Unknown arg: $1"; _usage >&2; exit 2 ;;
        esac
    done
    [[ -n "$input" ]] || { tbm_error "-i DIR required"; _usage >&2; exit 2; }
    [[ -d "$input" ]] || { tbm_error "Not a directory: $input"; exit 2; }

    input="$(cd "$input" && pwd -P)"
    local metadir="${input}/metadata"
    local action
    (( copy )) && action="copy" || action="move"

    local count=0 f rel dest
    while IFS= read -r f; do
        rel="$(basename "$f")"
        dest="${metadir}/${rel}"
        if (( dry )); then
            tbm_info "[dry-run] would $action: $rel -> metadata/$rel"
        else
            mkdir -p "$metadir"
            if (( copy )); then
                cp "$f" "$dest"
            else
                mv "$f" "$dest"
            fi
            tbm_ok "${action}d: $rel -> metadata/"
        fi
        count=$((count+1))
    done < <(_find_metadata_sidecars "$input")

    if (( count == 0 )); then
        tbm_info "no metadata sidecars found at top level of $input"
    else
        tbm_info "done: $count sidecars organized into metadata/"
    fi
}

main "$@"
