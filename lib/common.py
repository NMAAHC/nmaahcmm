"""Shared helpers for bleakleymm TBM workflows."""
from __future__ import annotations

import logging
import shutil
import signal
import sys
from datetime import datetime

_COLORS = {
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "reset": "\033[0m",
}


class _ColorFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.INFO: "blue",
        logging.WARNING: "yellow",
        logging.ERROR: "red",
    }

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        level_map = {logging.INFO: "INFO ", logging.WARNING: "WARN ", logging.ERROR: "ERROR"}
        level = level_map.get(record.levelno, record.levelname)
        msg = f"[{ts}] [{level}] {record.getMessage()}"
        if sys.stdout.isatty():
            c = self.LEVEL_COLORS.get(record.levelno)
            if c:
                msg = f"{_COLORS[c]}{msg}{_COLORS['reset']}"
        return msg


def get_logger(name: str = "tbm") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        h = logging.StreamHandler()
        h.setFormatter(_ColorFormatter())
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
    return logger


def require(*deps: str) -> None:
    log = get_logger()
    missing = [d for d in deps if shutil.which(d) is None]
    if missing:
        for d in missing:
            log.error(f"Missing dependency: {d}")
        sys.exit(1)


def require_one_of(*deps: str) -> str:
    for d in deps:
        if shutil.which(d):
            return d
    get_logger().error(f"Missing dependency: need one of: {', '.join(deps)}")
    sys.exit(1)


def install_sigterm_trap() -> None:
    def _handler(signum, frame):
        get_logger().error("Interrupted")
        sys.exit(130)

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


def run_id() -> str:
    return datetime.now().strftime("%Y%m%dT%H%M%S")


TBM_SIDECAR_SUFFIXES = (
    ".md5.txt", ".sha1.txt", ".sha224.txt", ".sha256.txt",
    ".sha384.txt", ".sha512.txt", ".crc32.txt", ".framemd5",
    ".mediainfo.txt", ".mediainfo.json", ".mediatrace.xml",
    ".ffprobe.json", ".exiftool.txt", ".exiftool.json",
    "_access.mp4",
    ".access.mp4",  # legacy access-copy name, kept so old outputs are still skipped
)


def is_sidecar(name: str) -> bool:
    return any(name.endswith(s) for s in TBM_SIDECAR_SUFFIXES)
