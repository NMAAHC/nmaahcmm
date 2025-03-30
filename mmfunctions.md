# nmaahcmmfunctions - Function Reference Guide

This document provides a quick-reference guide to the shared shell functions defined in the `nmaahcmmfunctions` script. These functions support the NMAAHC Media Microservices environment and are sourced in scripts like `nmaahcmmconfig`, `gmconfig`, and others.

---

## 🛠️ Utility & Setup Functions

### `_setcolors()`
**Purpose:** Initializes terminal color variables using `tput`.
- No arguments.
- Defines variables for white, red, yellow, gray, and reset.

---

### `_initialize_make()`
**Purpose:** Sets up safe handling for termination signals (e.g. Ctrl+C).
- Installs traps for `SIGHUP`, `SIGINT`, and `SIGTERM`.
- On interruption, logs and exits cleanly via `_cleanup()`.

---

### `_maketemp()` → `string`
**Purpose:** Creates a temporary file in `/tmp/` using `mktemp`.
- Exits the script if file creation fails.
- Logs error using `_report` and `_writeerrorlog`.

---

### `_mkdir(dir: string)`
**Purpose:** Safe `mkdir -p` wrapper.
- Accepts one or more directory paths.
- If creation fails, logs and exits.

---

## 🧼 Clean-up & Sorting

### `_removehidden(dir: string)`
**Purpose:** Removes hidden files (`.*`) inside a given directory.
- Uses `find` and `rm -vfr`.
- If no argument is given:
  ```bash
  cowsay "no argument provided to remove hidden files. tootles."
  ```

---

### `_sortk2(file: string)`
**Purpose:** Sorts a file by the second column.
- Uses `sort -k 2 -o` to overwrite in-place.
- Messages are delivered via `cowsay`:
  - If missing input: `"no argument provided to sort. tootles."`
  - On success: `"file sorting is done. tootles."`

---

## 🧪 Config & Dependency Checks

### `_check_dependencies(commands: string...)`
**Purpose:** Checks if required commands are installed.
- Takes one or more command names (e.g. `rsync`, `ffmpeg`).
- If not found, prints installation suggestions.
- Fails the script if any dependency is unmet.

---

### `_check_deliverdir()`
**Purpose:** Verifies that `$DELIVERDIR` exists.
- If not, prints a warning via `_report`.

---

## 🧰 Configuration Interfaces

### `_pashua_run()`
**Purpose:** Interface to run a GUI form using [Pashua](https://www.bluem.net/en/projects/pashua/) (macOS only).
- Searches multiple paths for the `Pashua` binary.
- Attempts Homebrew install if not found.
- Parses form results into shell variables.

---

## 📣 Logging, Reporting, and Time

### `_report([flags], message: string)`
**Purpose:** Prints terminal output with optional formatting and logging.
- Flags:
  - `-g` Green (declaration)
  - `-r` Red (warning + logs it)
  - `-b` Blue (question)
  - `-s` Prefix with script name
  - `-t` Prefix with timestamp
  - `-n` No newline
- If `-r` is used, logs the warning automatically.

---

### `_log([flag], message: string)`
**Purpose:** Logs messages to `nmaahcmm.log`.
- Flags:
  - `-b` Beginning of script
  - `-e` End of script
  - `-a` Abort
  - `-c` Comment
  - `-w` Warning
- Output format: `timestamp, script, status, op, mediaid, note`

---

### `_writelog(key: string, value: string)`
**Purpose:** Writes YAML-style key-value entries to an ingest log.
- If the `-t` flag is used, logs the current timestamp as the value.

---

### `_seconds_to_hhmmss(seconds: int)` → `string`
**Purpose:** Converts a total number of seconds into HH:MM:SS format.
- Example: `3661` → `01:01:01`

---

### `_check_rsync_output()`
**Purpose:** Increments `RSYNC_ERROR_COUNT` if the last `rsync` call failed.
- Uses `$?` to check exit code.

---

## 🐄 cowsay Humor

The following functions use `cowsay` for friendly feedback:
- `_removehidden`
- `_sortk2`

🐄 Sample output:
```bash
cowsay "file sorting is done. tootles."
cowsay "no argument provided to sort. tootles."
```

---

## 🧑‍💻 Developer Tips
- This script is meant to be **sourced**, not executed.
- It acts as a **function library** for TBM scripts.
- Combine with: `SCRIPT_PATH="${0%/*}" ; . "${SCRIPT_PATH}/nmaahcmmfunctions"`

---

Let us know if you'd like:
- Docstring headers added directly into the code
- Auto-generated tests or examples for each function
- More cowsay sass 🐮

