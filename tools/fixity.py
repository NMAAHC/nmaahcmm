#!/usr/bin/env python3
"""fixity.py - make (default) or verify hash sidecars for TBM files."""
from __future__ import annotations

import argparse
import hashlib
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import get_logger, install_sigterm_trap, is_sidecar  # noqa: E402

log = get_logger()

SUPPORTED_ALGOS = ("md5", "sha1", "sha256", "sha512", "crc32")

if sys.stdout.isatty():
    BOLD = "\033[1m"; BLUE = "\033[34m"; CYAN = "\033[36m"
    GREEN = "\033[32m"; YELLOW = "\033[33m"; DIM = "\033[2m"; RESET = "\033[0m"
else:
    BOLD = BLUE = CYAN = GREEN = YELLOW = DIM = RESET = ""


def print_usage(to=sys.stdout):
    print(f"{BOLD}{BLUE}USAGE:{RESET}", file=to)
    print(f"  {GREEN}fixity.py{RESET} {CYAN}-i{RESET} {YELLOW}PATH{RESET} [{YELLOW}PATH{RESET} ...] [options]", file=to)
    print(file=to)
    print(f"Run {GREEN}fixity.py{RESET} {CYAN}-h{RESET} for detailed help.", file=to)


def print_help():
    print(f"""{BOLD}{BLUE}NAME{RESET}
  {GREEN}fixity.py{RESET} — make or verify hash sidecars for files

{BOLD}{BLUE}USAGE{RESET}
  {GREEN}fixity.py{RESET} {CYAN}-i{RESET} {YELLOW}PATH{RESET} [{YELLOW}PATH{RESET} ...] [{CYAN}-a{RESET} {YELLOW}ALGO{RESET}] [{CYAN}-p{RESET}] [{CYAN}-r{RESET}|{CYAN}-A{RESET}] [{CYAN}-n{RESET}]   {DIM}# make (default){RESET}
  {GREEN}fixity.py{RESET} {CYAN}-i{RESET} {YELLOW}PATH{RESET} [{YELLOW}PATH{RESET} ...] [{CYAN}-a{RESET} {YELLOW}ALGO{RESET}] {CYAN}--verify{RESET}                   {DIM}# verify{RESET}

{BOLD}{BLUE}OPTIONS{RESET}
  {CYAN}-i{RESET} {YELLOW}PATH{RESET} [{YELLOW}PATH{RESET} ...]     One or more files or directories (directories are recursed)
  {CYAN}-a{RESET}, {CYAN}--algorithm{RESET} {YELLOW}ALGO{RESET}   Hash algorithm: {YELLOW}md5{RESET} (default), {YELLOW}sha1{RESET}, {YELLOW}sha256{RESET}, {YELLOW}sha512{RESET}, {YELLOW}crc32{RESET}
  {CYAN}-c{RESET}, {CYAN}--verify{RESET}            Verify existing sidecars (auto-detects combined or per-file)
  {CYAN}-p{RESET}, {CYAN}--per-file{RESET}          Directory input: write a sidecar per source file
  {CYAN}-r{RESET}, {CYAN}--relative{RESET}          Combined mode: store paths relative to the input dir
  {CYAN}-A{RESET}, {CYAN}--absolute{RESET}          Combined mode: store absolute paths
  {CYAN}-n{RESET}, {CYAN}--dry-run{RESET}           Print planned actions, write nothing
  {CYAN}-h{RESET}, {CYAN}--help{RESET}              Show this help

{BOLD}{BLUE}EXAMPLES{RESET}
  {DIM}# MD5 sidecar for a single file{RESET}
  {GREEN}fixity.py{RESET} {CYAN}-i{RESET} /Volumes/archive/<file>

  {DIM}# MD5 sidecars for several files at once{RESET}
  {GREEN}fixity.py{RESET} {CYAN}-i{RESET} a.mp3 b.mp3 c.mp3

  {DIM}# One combined MD5 manifest for a directory (default){RESET}
  {GREEN}fixity.py{RESET} {CYAN}-i{RESET} /Volumes/archive/<dir>

  {DIM}# Per-file SHA-256 sidecars inside a directory{RESET}
  {GREEN}fixity.py{RESET} {CYAN}-i{RESET} /Volumes/archive/<dir> {CYAN}-a{RESET} sha256 {CYAN}-p{RESET}

  {DIM}# Combined manifest with relative paths{RESET}
  {GREEN}fixity.py{RESET} {CYAN}-i{RESET} /Volumes/archive/<dir> {CYAN}-r{RESET}

  {DIM}# Verify (auto-detects combined or per-file){RESET}
  {GREEN}fixity.py{RESET} {CYAN}-i{RESET} /Volumes/archive/<dir> {CYAN}--verify{RESET}

{BOLD}{BLUE}SIDECAR FORMAT{RESET}
  Per-file (single file or {CYAN}-p{RESET}):
    One sidecar per source file: {YELLOW}<file>.<algo>.txt{RESET}
    Single-line content: {YELLOW}<hash>  <basename>{RESET}

  Combined (directory input, default):
    One manifest inside the directory: {YELLOW}<dir>/<dirname>.<algo>.txt{RESET}
    One line per file: {YELLOW}<hash>  <path>{RESET}
    Path is the basename by default, relative with {CYAN}-r{RESET}, absolute with {CYAN}-A{RESET}.""")


def _hash_only(path: Path, algo: str) -> str:
    if algo == "crc32":
        c = 0
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                c = zlib.crc32(chunk, c)
        return f"{c:08x}"
    h = hashlib.new(algo)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def _entry_path(file: Path, root: Path, mode: str) -> str:
    if mode == "absolute":
        return str(file)
    if mode == "relative":
        return str(file.relative_to(root))
    return file.name


def do_make_per_file(input_: Path, algo: str, dry_run: bool) -> int:
    count = skipped = 0
    for f in _iter_source_files(input_):
        sidecar = f.with_name(f.name + f".{algo}.txt")
        if sidecar.exists():
            log.info(f"skip (sidecar exists): {f}")
            skipped += 1
            continue
        if dry_run:
            log.info(f"[dry-run] would write: {sidecar}")
        else:
            h = _hash_only(f, algo)
            sidecar.write_text(f"{h}  {f.name}\n")
            log.info(f"wrote {sidecar}")
        count += 1
    log.info(f"done: {count} processed, {skipped} skipped (algorithm: {algo}, per-file)")
    return 0


def do_make_combined(input_: Path, algo: str, dry_run: bool, path_mode: str) -> int:
    name = input_.name
    manifest = input_ / f"{name}.{algo}.txt"
    if manifest.exists() and not dry_run:
        log.warning(f"manifest exists, overwriting: {manifest}")

    lines: list[str] = []
    count = 0
    for f in _iter_source_files(input_):
        entry = _entry_path(f, input_, path_mode)
        if dry_run:
            log.info(f"[dry-run] would hash: {entry}")
        else:
            h = _hash_only(f, algo)
            lines.append(f"{h}  {entry}\n")
            log.info(f"hashed: {entry}")
        count += 1

    if dry_run:
        log.info(f"[dry-run] would write manifest: {manifest} ({count} entries)")
    else:
        manifest.write_text("".join(lines))
        log.info(f"wrote {manifest} ({count} entries, path-mode: {path_mode})")
    return 0


def do_verify_per_file(input_: Path, algo: str) -> int:
    ok = failed = missing = 0
    for f in _iter_source_files(input_):
        sidecar = f.with_name(f.name + f".{algo}.txt")
        if not sidecar.exists():
            log.warning(f"no {algo} sidecar: {f}")
            missing += 1
            continue
        fields = sidecar.read_text().split()
        if not fields:
            log.error(f"MISMATCH: {f} (sidecar is empty: {sidecar})")
            failed += 1
            continue
        expected = fields[0]
        actual = _hash_only(f, algo)
        if expected == actual:
            log.info(f"match: {f}")
            ok += 1
        else:
            log.error(f"MISMATCH: {f} (expected {expected}, got {actual})")
            failed += 1
    log.info(f"verify: {ok} ok, {failed} failed, {missing} missing (algorithm: {algo}, per-file)")
    return 1 if failed else 0


def do_verify_combined(manifest: Path, input_: Path, algo: str) -> int:
    ok = failed = missing = 0
    for line in manifest.read_text().splitlines():
        if not line.strip():
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2:
            log.warning(f"skipping malformed line: {line}")
            continue
        h, entry = parts
        file = Path(entry) if Path(entry).is_absolute() else (input_ / entry)
        if not file.is_file():
            log.warning(f"missing file: {file} (entry: {entry})")
            missing += 1
            continue
        actual = _hash_only(file, algo)
        if h == actual:
            log.info(f"match: {file}")
            ok += 1
        else:
            log.error(f"MISMATCH: {file} (expected {h}, got {actual})")
            failed += 1
    log.info(f"verify: {ok} ok, {failed} failed, {missing} missing (algorithm: {algo}, manifest: {manifest})")
    return 1 if failed else 0


def do_verify_auto(input_: Path, algo: str) -> int:
    if input_.is_file():
        return do_verify_per_file(input_, algo)
    manifest = input_ / f"{input_.name}.{algo}.txt"
    if manifest.is_file():
        return do_verify_combined(manifest, input_, algo)
    log.info("no combined manifest found, falling back to per-file")
    return do_verify_per_file(input_, algo)


def main() -> int:
    install_sigterm_trap()
    argv = sys.argv[1:]
    if not argv:
        print_usage()
        return 0

    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("-i", "--input", nargs="+")
    p.add_argument("-a", "--algorithm", default="md5", choices=SUPPORTED_ALGOS)
    p.add_argument("-c", "--verify", action="store_true")
    p.add_argument("-n", "--dry-run", action="store_true")
    p.add_argument("-p", "--per-file", action="store_true")
    p.add_argument("-r", "--relative", action="store_true")
    p.add_argument("-A", "--absolute", action="store_true")
    p.add_argument("-h", "--help", action="store_true")

    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 2

    if args.help:
        print_help()
        return 0
    if not args.input:
        log.error("-i PATH required")
        print_usage(to=sys.stderr)
        return 2
    if args.relative and args.absolute:
        log.error("--relative and --absolute are mutually exclusive")
        return 2
    if args.per_file and (args.relative or args.absolute):
        log.error("--relative/--absolute don't apply to --per-file mode")
        return 2
    if args.verify and args.dry_run:
        log.error("--dry-run is not valid with --verify")
        return 2

    inputs = [Path(i) for i in args.input]

    # Validate every input up front so a bad path can't abort a half-finished run.
    for path in inputs:
        if not path.is_file() and not path.is_dir():
            log.error(f"Not a file or directory: {path}")
            return 2
        if path.is_file() and (args.relative or args.absolute):
            log.error(f"--relative/--absolute only apply to directory input: {path}")
            return 2

    status = 0
    for path in inputs:
        if path.is_dir():
            path = path.resolve()
        if args.verify:
            rc = do_verify_auto(path, args.algorithm)
        elif path.is_file() or args.per_file:
            rc = do_make_per_file(path, args.algorithm, args.dry_run)
        else:
            mode = "relative" if args.relative else "absolute" if args.absolute else "basename"
            rc = do_make_combined(path, args.algorithm, args.dry_run, mode)
        if rc:
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
