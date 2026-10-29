# Shared helpers for bleakleymm TBM workflows. Source, don't execute.

_tbm_color() {
    if [[ ! -t 1 ]]; then shift; printf '%s\n' "$*"; return; fi
    local c="$1"; shift
    case "$c" in
        red)    printf '\033[31m%s\033[0m\n' "$*" ;;
        green)  printf '\033[32m%s\033[0m\n' "$*" ;;
        yellow) printf '\033[33m%s\033[0m\n' "$*" ;;
        blue)   printf '\033[34m%s\033[0m\n' "$*" ;;
        *)      printf '%s\n' "$*" ;;
    esac
}

tbm_info()  { _tbm_color blue   "[$(date +%FT%T)] [INFO]  $*"; }
tbm_ok()    { _tbm_color green  "[$(date +%FT%T)] [OK]    $*"; }
tbm_warn()  { _tbm_color yellow "[$(date +%FT%T)] [WARN]  $*" >&2; }
tbm_error() { _tbm_color red    "[$(date +%FT%T)] [ERROR] $*" >&2; }

tbm_require() {
    local missing=0 dep
    for dep in "$@"; do
        command -v "$dep" >/dev/null 2>&1 || { tbm_error "Missing dependency: $dep"; missing=1; }
    done
    [[ $missing -eq 0 ]] || exit 1
}

tbm_require_one_of() {
    local dep
    for dep in "$@"; do
        command -v "$dep" >/dev/null 2>&1 && { printf '%s\n' "$dep"; return 0; }
    done
    tbm_error "Missing dependency: need one of: $*"
    exit 1
}

tbm_trap_sigterm() { trap 'tbm_error "Interrupted"; exit 130' INT TERM; }

tbm_run_id() { date +%Y%m%dT%H%M%S; }

# Known sidecar filename suffixes produced by tools in this repo.
# Iteration helpers skip these so sidecars aren't reprocessed as sources.
TBM_SIDECAR_SUFFIXES=(
    .md5.txt .sha1.txt .sha224.txt .sha256.txt .sha384.txt .sha512.txt .crc32.txt .framemd5
    .mediainfo.txt .mediainfo.json .mediatrace.xml .ffprobe.json .exiftool.txt .exiftool.json
    _access.mp4
    .access.mp4  # legacy access-copy name, kept so old outputs are still skipped
)

tbm_is_sidecar() {
    local name="$1" suf
    for suf in "${TBM_SIDECAR_SUFFIXES[@]}"; do
        [[ "$name" == *"$suf" ]] && return 0
    done
    return 1
}
