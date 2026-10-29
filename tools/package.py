#!/usr/bin/env python3
"""package.py - tidy a directory by moving metadata sidecars into a metadata/ subfolder.

Everything else (source files, access copies, checksum sidecars) stays flat.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import get_logger, install_sigterm_trap  # noqa: E402

log = get_logger()

METADATA_SUFFIXES = (
    ".mediainfo.txt", ".mediainfo.json", ".mediatrace.xml",
    ".ffprobe.json",
    ".exiftool.txt", ".exiftool.json",
)

if sys.stdout.isatty():
    BOLD = "\033[1m"; BLUE = "\033[34m"; CYAN = "\033[36m"
    GREEN = "\033[32m"; YELLOW = "\033[33m"; DIM = "\033[2m"; RESET = "\033[0m"
else:
    BOLD = BLUE = CYAN = GREEN = YELLOW = DIM = RESET = ""


def print_usage(to=sys.stdout):
    print(f"{BOLD}{BLUE}USAGE:{RESET}", file=to)
    print(f"  {GREEN}package.py{RESET} {CYAN}-i{RESET} {YELLOW}DIR{RESET} [{CYAN}-n{RESET}] [{CYAN}--copy{RESET}]", file=to)
    print(file=to)
    print(f"Run {GREEN}package.py{RESET} {CYAN}-h{RESET} for detailed help.", file=to)


def print_help():
    print(f"""{BOLD}{BLUE}NAME{RESET}
  {GREEN}package.py{RESET} — tidy a directory by moving metadata sidecars into {YELLOW}metadata/{RESET}

{BOLD}{BLUE}USAGE{RESET}
  {GREEN}package.py{RESET} {CYAN}-i{RESET} {YELLOW}DIR{RESET} [{CYAN}-n{RESET}] [{CYAN}--copy{RESET}]

{BOLD}{BLUE}OPTIONS{RESET}
  {CYAN}-i{RESET} {YELLOW}DIR{RESET}            Directory to tidy (in-place)
  {CYAN}-n{RESET}, {CYAN}--dry-run{RESET}      Print planned moves, don't touch anything
  {CYAN}--copy{RESET}             Copy sidecars into {YELLOW}metadata/{RESET} instead of moving
  {CYAN}-h{RESET}, {CYAN}--help{RESET}         Show this help

{BOLD}{BLUE}WHAT MOVES{RESET}
  These suffixes move into {YELLOW}DIR/metadata/{RESET}:
    {YELLOW}*.mediainfo.txt   *.mediainfo.json   *.mediatrace.xml{RESET}
    {YELLOW}*.ffprobe.json{RESET}
    {YELLOW}*.exiftool.txt    *.exiftool.json{RESET}

{BOLD}{BLUE}WHAT STAYS{RESET}
  Source files, checksum sidecars ({YELLOW}*.md5.txt{RESET}, {YELLOW}*.sha256.txt{RESET}, ...) and access
  copies ({YELLOW}*_access.mp4{RESET}) stay flat at the top level.

{BOLD}{BLUE}SCOPE{RESET}
  Operates at the top level of {YELLOW}DIR{RESET} only (no recursion). Running twice is
  safe — the second run just sees no sidecars left to move.

{BOLD}{BLUE}EXAMPLES{RESET}
  {DIM}# Tidy a directory{RESET}
  {GREEN}package.py{RESET} {CYAN}-i{RESET} /Volumes/archive/<dir>

  {DIM}# Preview what would move{RESET}
  {GREEN}package.py{RESET} {CYAN}-i{RESET} /Volumes/archive/<dir> {CYAN}-n{RESET}

  {DIM}# Copy instead of move (keep originals alongside){RESET}
  {GREEN}package.py{RESET} {CYAN}-i{RESET} /Volumes/archive/<dir> {CYAN}--copy{RESET}""")


def _is_metadata_sidecar(name: str) -> bool:
    return any(name.endswith(s) for s in METADATA_SUFFIXES)


def _find_metadata_sidecars(root: Path) -> list[Path]:
    return sorted(
        p for p in root.iterdir()
        if p.is_file() and _is_metadata_sidecar(p.name)
    )


def main() -> int:
    install_sigterm_trap()
    argv = sys.argv[1:]
    if not argv:
        print_usage()
        return 0

    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("-i", "--input")
    p.add_argument("-n", "--dry-run", action="store_true")
    p.add_argument("--copy", action="store_true")
    p.add_argument("-h", "--help", action="store_true")

    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 2

    if args.help:
        print_help()
        return 0
    if not args.input:
        log.error("-i DIR required")
        print_usage(to=sys.stderr)
        return 2

    root = Path(args.input)
    if not root.is_dir():
        log.error(f"Not a directory: {root}")
        return 2
    root = root.resolve()

    metadir = root / "metadata"
    action = "copy" if args.copy else "move"

    count = 0
    for f in _find_metadata_sidecars(root):
        dest = metadir / f.name
        if args.dry_run:
            log.info(f"[dry-run] would {action}: {f.name} -> metadata/{f.name}")
        else:
            metadir.mkdir(exist_ok=True)
            if args.copy:
                shutil.copy2(f, dest)
            else:
                shutil.move(str(f), str(dest))
            log.info(f"{action}d: {f.name} -> metadata/")
        count += 1

    if count == 0:
        log.info(f"no metadata sidecars found at top level of {root}")
    else:
        log.info(f"done: {count} sidecars organized into metadata/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
