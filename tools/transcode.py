#!/usr/bin/env python3
"""transcode.py - make H.265 (HEVC) MP4 access copies alongside source files."""
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import get_logger, install_sigterm_trap, is_sidecar, require  # noqa: E402

log = get_logger()

X265_CRF = "28"
X265_PRESET = "medium"
AAC_BITRATE = "192k"

if sys.stdout.isatty():
    BOLD = "\033[1m"; BLUE = "\033[34m"; CYAN = "\033[36m"
    GREEN = "\033[32m"; YELLOW = "\033[33m"; DIM = "\033[2m"; RESET = "\033[0m"
else:
    BOLD = BLUE = CYAN = GREEN = YELLOW = DIM = RESET = ""


def print_usage(to=sys.stdout):
    print(f"{BOLD}{BLUE}USAGE:{RESET}", file=to)
    print(f"  {GREEN}transcode.py{RESET} {CYAN}-i{RESET} {YELLOW}PATH{RESET} [{CYAN}-o{RESET} {YELLOW}OUTPUT{RESET}] [{CYAN}-n{RESET}] [{CYAN}--force{RESET}]", file=to)
    print(file=to)
    print(f"Run {GREEN}transcode.py{RESET} {CYAN}-h{RESET} for detailed help.", file=to)


def print_help():
    print(f"""{BOLD}{BLUE}NAME{RESET}
  {GREEN}transcode.py{RESET} — make H.265 MP4 access copies alongside source files

{BOLD}{BLUE}USAGE{RESET}
  {GREEN}transcode.py{RESET} {CYAN}-i{RESET} {YELLOW}PATH{RESET} [{CYAN}-o{RESET} {YELLOW}OUTPUT{RESET}] [{CYAN}-n{RESET}] [{CYAN}--force{RESET}]

{BOLD}{BLUE}OPTIONS{RESET}
  {CYAN}-i{RESET} {YELLOW}PATH{RESET}            File or directory (directory is recursed)
  {CYAN}-o{RESET} {YELLOW}OUTPUT{RESET}          Output file path (single file input only).
                     Default: sibling file {YELLOW}<file>_access.mp4{RESET} (source extension dropped).
  {CYAN}-n{RESET}, {CYAN}--dry-run{RESET}       Print the ffmpeg command, don't run it
  {CYAN}--force{RESET}             Overwrite existing {YELLOW}_access.mp4{RESET} outputs
  {CYAN}-h{RESET}, {CYAN}--help{RESET}          Show this help

{BOLD}{BLUE}ENCODER{RESET}
  {YELLOW}ffmpeg -c:v libx265 -crf {X265_CRF} -preset {X265_PRESET} -tag:v hvc1{RESET}
  {YELLOW}       -c:a aac -b:a {AAC_BITRATE} -movflags +faststart{RESET}
  (the {YELLOW}hvc1{RESET} tag makes the file play in QuickTime/Safari.)

{BOLD}{BLUE}EXAMPLES{RESET}
  {DIM}# Access copy for a single file{RESET}
  {GREEN}transcode.py{RESET} {CYAN}-i{RESET} /Volumes/archive/<file>

  {DIM}# Batch a whole directory{RESET}
  {GREEN}transcode.py{RESET} {CYAN}-i{RESET} /Volumes/archive/<dir>

  {DIM}# Custom output path (single file){RESET}
  {GREEN}transcode.py{RESET} {CYAN}-i{RESET} master.mkv {CYAN}-o{RESET} /tmp/preview.mp4

  {DIM}# See the command without running{RESET}
  {GREEN}transcode.py{RESET} {CYAN}-i{RESET} /Volumes/archive/<dir> {CYAN}-n{RESET}

{BOLD}{BLUE}OUTPUT{RESET}
  Per source file: {YELLOW}<file>_access.mp4{RESET} next to the source, where {YELLOW}<file>{RESET}
  is the source name without its extension (master.mov -> master_access.mp4).
  Existing outputs are skipped unless {CYAN}--force{RESET} is given.""")


def _iter_source_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if root.is_dir():
        return sorted(
            p for p in root.rglob("*")
            if p.is_file() and not is_sidecar(p.name)
        )
    log.error(f"Not a file or directory: {root}")
    sys.exit(2)


def _ffmpeg_cmd(in_: Path, out: Path) -> list[str]:
    return [
        "ffmpeg", "-hide_banner", "-nostdin", "-y",
        "-i", str(in_),
        "-c:v", "libx265", "-crf", X265_CRF, "-preset", X265_PRESET, "-tag:v", "hvc1",
        "-c:a", "aac", "-b:a", AAC_BITRATE,
        "-movflags", "+faststart",
        str(out),
    ]


def transcode_one(in_: Path, out: Path, dry: bool, force: bool) -> bool:
    if out.exists() and not force:
        log.info(f"skip (exists): {out}")
        return True
    cmd = _ffmpeg_cmd(in_, out)
    if dry:
        log.info("[dry-run] " + " ".join(shlex.quote(c) for c in cmd))
        return True
    log.info(f"transcoding: {in_} -> {out}")
    try:
        subprocess.run(cmd, stdin=subprocess.DEVNULL, check=True)
        log.info(f"wrote {out}")
        return True
    except subprocess.CalledProcessError:
        log.error(f"ffmpeg failed: {in_}")
        out.unlink(missing_ok=True)
        return False


def main() -> int:
    install_sigterm_trap()
    argv = sys.argv[1:]
    if not argv:
        print_usage()
        return 0

    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("-i", "--input")
    p.add_argument("-o", "--output")
    p.add_argument("-n", "--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("-h", "--help", action="store_true")

    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 2

    if args.help:
        print_help()
        return 0
    if not args.input:
        log.error("-i INPUT required")
        print_usage(to=sys.stderr)
        return 2

    in_path = Path(args.input)
    if args.output and not in_path.is_file():
        log.error("-o is only valid with a single-file -i")
        return 2

    require("ffmpeg")

    if in_path.is_dir():
        in_path = in_path.resolve()

    total = failed = 0
    for f in _iter_source_files(in_path):
        total += 1
        out = Path(args.output) if args.output else f.with_name(f.stem + "_access.mp4")
        if not transcode_one(f, out, args.dry_run, args.force):
            failed += 1

    log.info(f"summary: {total - failed}/{total} succeeded")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
