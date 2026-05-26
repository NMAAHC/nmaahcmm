Digital time-based-media (audio/video) processing tools. Five small tools,
each shipped in two flavors — `tools/<name>.sh` and `tools/<name>.py` — that
accept the same flags and write the same output files. Use whichever
language is more comfortable.

## Requirements

- `bash` 4+ or `zsh`, and `python3` 3.9+
- External binaries (install per tool as needed):
  - `ffmpeg` / `ffprobe` — used by transcode, validate, metadata
  - `mediainfo` — used by metadata, validate
  - `exiftool` — used by metadata
  - `mediaconch` — used by validate

macOS:

```sh
brew install ffmpeg mediainfo exiftool mediaconch
```

Each tool only checks for the dependencies it actually needs at run time,
so `metadata --no-exiftool` won't fail on a missing exiftool, for example.

## Tools at a glance

| Tool        | What it does                                               |
|-------------|------------------------------------------------------------|
| `fixity`    | Make or verify hash sidecars (md5/sha1/sha256/sha512/crc32) |
| `metadata`  | Extract mediainfo / ffprobe / exiftool sidecars            |
| `validate`  | Check each file against a MediaConch policy + ffprobe      |
| `transcode` | Make H.265 MP4 access copies                               |
| `package`   | Move metadata sidecars into a `metadata/` subfolder        |

All tools follow the same conventions:

- Run with no args → short usage
- Run with `-h` / `--help` → detailed colored help
- `-i PATH` is the input file or directory
- `-n` / `--dry-run` previews without writing (where applicable)

## Tools

### fixity

```sh
tools/fixity.sh -i PATH [-a ALGO] [-p] [-r|-A] [-n]     # make (default)
tools/fixity.sh -i PATH [-a ALGO] --verify              # verify
```

Default on a directory: one combined manifest at `<dir>/<dirname>.<algo>.txt`
with basenames as paths. Use `-p` for per-file sidecars, `-r` for relative
paths, `-A` for absolute paths. `--verify` auto-detects combined vs per-file.

### metadata

```sh
tools/metadata.sh -i PATH [--mediatrace] [--ee2|--ee3] [--no-mediainfo] [--no-ffprobe] [--no-exiftool]
```

Writes five sidecars by default, next to each source file:

- `<file>.mediainfo.txt`, `<file>.mediainfo.json`
- `<file>.ffprobe.json`
- `<file>.exiftool.txt`, `<file>.exiftool.json`

`--mediatrace` adds `<file>.mediatrace.xml`. `--ee2` / `--ee3` deepen
exiftool's embedded-stream extraction.

### validate

```sh
tools/validate.sh -i PATH [--policy POLICY.xml]
```

Runs MediaConch against `policies/default.xml` (a loose placeholder —
supply a real format-specific policy with `--policy` for preservation-grade
validation) and confirms ffprobe can parse each file. No sidecars written;
exits non-zero if any file fails.

### transcode

```sh
tools/transcode.sh -i PATH [-o OUTPUT] [-n] [--force]
```

Produces `<file>.access.mp4` next to each source using
`libx265 -crf 28 -preset medium -tag:v hvc1` + AAC 192k with `+faststart`.
The `hvc1` tag makes the file play in QuickTime and Safari. Skips existing
outputs unless `--force`.

### package

```sh
tools/package.sh -i DIR [-n] [--copy]
```

Moves metadata sidecars (the `metadata` tool's outputs) into `DIR/metadata/`.
Source files, checksum sidecars, and access copies stay flat. Re-running is
a no-op.

## Typical pipeline

```sh
DIR=/Volumes/archive/my_package

# 1. Extract metadata
./tools/metadata.sh -i "$DIR"

# 2. Make H.265 access copies
./tools/transcode.sh -i "$DIR"

# 3. Validate against a real preservation policy
./tools/validate.sh -i "$DIR" --policy ~/policies/my-ffv1.xml

# 4. Compute a combined SHA-256 manifest
./tools/fixity.sh -i "$DIR" -a sha256

# 5. Tidy metadata sidecars into metadata/
./tools/package.sh -i "$DIR"
```

## Notes

- **Parity.** Bash and Python versions write byte-identical output files
  (hashes, ffmpeg outputs, captured tool stdout, etc.) so the two can
  round-trip each other's output.
- **Sidecar skip list.** Every tool skips files matching any known sidecar
  suffix during directory iteration — so re-runs don't produce checksums
  of checksums, etc. The list lives in `lib/common.sh` / `lib/common.py`.
- **Shared library.** `lib/common.{sh,py}` provides colored logging,
  dependency checks, a sigterm trap, and the sidecar-suffix list. Each
  tool sources it.

