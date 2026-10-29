#!/usr/bin/env bash
# transcode.sh - make H.265 (HEVC) MP4 access copies alongside source files.

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

# Encoder settings (H.265 MP4 access copy)
X265_CRF=28
X265_PRESET=medium
AAC_BITRATE=192k

_usage() {
    cat <<EOF
${BOLD}${BLUE}USAGE:${RESET}
  ${GREEN}transcode.sh${RESET} ${CYAN}-i${RESET} ${YELLOW}PATH${RESET} [${CYAN}-o${RESET} ${YELLOW}OUTPUT${RESET}] [${CYAN}-n${RESET}] [${CYAN}--force${RESET}]

Run ${GREEN}transcode.sh${RESET} ${CYAN}-h${RESET} for detailed help.
EOF
}

_help() {
    cat <<EOF
${BOLD}${BLUE}NAME${RESET}
  ${GREEN}transcode.sh${RESET} — make H.265 MP4 access copies alongside source files

${BOLD}${BLUE}USAGE${RESET}
  ${GREEN}transcode.sh${RESET} ${CYAN}-i${RESET} ${YELLOW}PATH${RESET} [${CYAN}-o${RESET} ${YELLOW}OUTPUT${RESET}] [${CYAN}-n${RESET}] [${CYAN}--force${RESET}]

${BOLD}${BLUE}OPTIONS${RESET}
  ${CYAN}-i${RESET} ${YELLOW}PATH${RESET}            File or directory (directory is recursed)
  ${CYAN}-o${RESET} ${YELLOW}OUTPUT${RESET}          Output file path (single file input only).
                     Default: sibling file ${YELLOW}<file>_access.mp4${RESET} (source extension dropped).
  ${CYAN}-n${RESET}, ${CYAN}--dry-run${RESET}       Print the ffmpeg command, don't run it
  ${CYAN}--force${RESET}             Overwrite existing ${YELLOW}_access.mp4${RESET} outputs
  ${CYAN}-h${RESET}, ${CYAN}--help${RESET}          Show this help

${BOLD}${BLUE}ENCODER${RESET}
  ${YELLOW}ffmpeg -c:v libx265 -crf ${X265_CRF} -preset ${X265_PRESET} -tag:v hvc1${RESET}
  ${YELLOW}       -c:a aac -b:a ${AAC_BITRATE} -movflags +faststart${RESET}
  (the ${YELLOW}hvc1${RESET} tag makes the file play in QuickTime/Safari.)

${BOLD}${BLUE}EXAMPLES${RESET}
  ${DIM}# Access copy for a single file${RESET}
  ${GREEN}transcode.sh${RESET} ${CYAN}-i${RESET} /Volumes/archive/<file>

  ${DIM}# Batch a whole directory${RESET}
  ${GREEN}transcode.sh${RESET} ${CYAN}-i${RESET} /Volumes/archive/<dir>

  ${DIM}# Custom output path (single file)${RESET}
  ${GREEN}transcode.sh${RESET} ${CYAN}-i${RESET} master.mkv ${CYAN}-o${RESET} /tmp/preview.mp4

  ${DIM}# See the command without running${RESET}
  ${GREEN}transcode.sh${RESET} ${CYAN}-i${RESET} /Volumes/archive/<dir> ${CYAN}-n${RESET}

${BOLD}${BLUE}OUTPUT${RESET}
  Per source file: ${YELLOW}<file>_access.mp4${RESET} next to the source, where ${YELLOW}<file>${RESET}
  is the source name without its extension (master.mov -> master_access.mp4).
  Existing outputs are skipped unless ${CYAN}--force${RESET} is given.
EOF
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

_ffmpeg_cmd() {
    local in="$1" out="$2"
    printf 'ffmpeg -hide_banner -nostdin -y -i %q -c:v libx265 -crf %s -preset %s -tag:v hvc1 -c:a aac -b:a %s -movflags +faststart %q' \
        "$in" "$X265_CRF" "$X265_PRESET" "$AAC_BITRATE" "$out"
}

_transcode_one() {
    local in="$1" out="$2" dry="$3" force="$4"
    if [[ -f "$out" ]] && (( ! force )); then
        tbm_info "skip (exists): $out"
        return 0
    fi
    if (( dry )); then
        tbm_info "[dry-run] $(_ffmpeg_cmd "$in" "$out")"
        return 0
    fi
    tbm_info "transcoding: $in -> $out"
    if ffmpeg -hide_banner -nostdin -y -i "$in" \
        -c:v libx265 -crf "$X265_CRF" -preset "$X265_PRESET" -tag:v hvc1 \
        -c:a aac -b:a "$AAC_BITRATE" -movflags +faststart "$out" \
        </dev/null; then
        tbm_ok "wrote $out"
        return 0
    fi
    tbm_error "ffmpeg failed: $in"
    rm -f "$out"
    return 1
}

main() {
    if [[ $# -eq 0 ]]; then _usage; exit 0; fi
    local input="" output="" dry=0 force=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -i) input="${2:-}"; shift 2 ;;
            -o) output="${2:-}"; shift 2 ;;
            -n|--dry-run) dry=1; shift ;;
            --force) force=1; shift ;;
            -h|--help) _help; exit 0 ;;
            *) tbm_error "Unknown arg: $1"; _usage >&2; exit 2 ;;
        esac
    done
    [[ -n "$input" ]] || { tbm_error "-i INPUT required"; _usage >&2; exit 2; }
    if [[ -n "$output" && ! -f "$input" ]]; then
        tbm_error "-o is only valid with a single-file -i"
        exit 2
    fi

    tbm_require ffmpeg

    local total=0 failed=0 f out base
    while IFS= read -r f; do
        total=$((total+1))
        if [[ -n "$output" ]]; then
            out="$output"
        else
            # Strip the extension from the basename only, so a dot in a
            # directory name can't truncate the path.
            base="$(basename "$f")"
            out="$(dirname "$f")/${base%.*}_access.mp4"
        fi
        _transcode_one "$f" "$out" "$dry" "$force" || failed=$((failed+1))
    done < <(_iter_source_files "$input")

    tbm_info "summary: $((total-failed))/$total succeeded"
    [[ $failed -eq 0 ]] || exit 1
}

main "$@"
