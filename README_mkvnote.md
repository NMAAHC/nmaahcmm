# MKV Metadata Tagging Script - `mkvnote`

## Overview

`mkvnote` is a Bash script designed to embed metadata tags into Matroska (MKV) video files using pre-defined sets of key-value pairs. It supports two metadata profiles, `JPC` (Johnson Publishing Company) and `NMAAHC` (National Museum of African American History and Culture), which have specific fields associated with them. The script can be run interactively or in batch mode using a CSV file to automate the tagging of multiple files.

## Key Features
- Supports two tag profiles: `JPC` and `NMAAHC`
- Interactive dialog interface for manual tagging
- Batch processing of MKV files via a CSV file
- Embeds custom metadata tags into MKV files using the `mkvpropedit` tool

## Prerequisites

Ensure you have the following installed on your macOS system:

- **Bash Shell**: The script is designed to be executed in a Bash environment.
- **Homebrew**: If you don't have Homebrew installed, you can install it using:
  ```bash
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  ```

- **MKVToolNix**: Required to embed the tags into MKV files. Install it via Homebrew:
  ```bash
  brew install mkvtoolnix
  ```

- **swiftDialog**: Required for the interactive dialog mode. Download and install it from:
  [https://github.com/swiftDialog/swiftDialog/releases](https://github.com/swiftDialog/swiftDialog/releases)

- **xmlstarlet**: Required to handle XML operations. Install it via Homebrew:
  ```bash
  brew install xmlstarlet
  ```

## Usage

The script can be used in two primary ways:
1. **Interactive Tagging via Dialog**
2. **Batch Tagging via CSV File**

### 1. Interactive Mode

To run the script interactively and manually input metadata for a single MKV file, use the following syntax:

```bash
./mkvnote [-p|--profile <profile>] /path/to/file.mkv
```

- **`-p|--profile`**: The profile to use for tagging. Must be either `jpc` or `nmaahc`.
- **`/path/to/file.mkv`**: The MKV file that you want to tag.

If the profile is not provided via the command line, the script will prompt you to select one interactively.

#### Example:

```bash
./mkvnote -p jpc /home/user/videos/sample.mkv
```

### 2. Batch Mode with CSV File

To tag multiple MKV files in batch mode using a CSV file, use the following syntax:

```bash
./mkvnote /path/to/file.csv
```

- The CSV file must contain the metadata for each file, with a column for the filename and other columns for metadata tags.

#### Example CSV Structure:

```csv
filename,director,rating
/home/user/videos/sample1.mkv,Dave,PG
/home/user/videos/sample2.mkv,Blake,G
```

The script will read each file from the CSV, apply the metadata tags, and embed them into the respective MKV files.

### Tag Profiles

#### JPC Profile:
- `COLLECTION`
- `TITLE`
- `CATALOG_NUMBER`
- `DESCRIPTION`
- `DATE_DIGITIZED`
- `ENCODING_SETTINGS`
- `ENCODED_BY`
- `ORIGINAL_MEDIA_TYPE`
- `DATE_TAGGED`
- `TERMS_OF_USE`
- `_TECHNICAL_NOTES`
- `_ORIGINAL_FPS`

#### NMAAHC Profile:
Includes all tags from the `JPC` profile, with an additional tag:
- `_TAGTAG`

### Tagging Example

In both interactive and batch modes, the tags are embedded into the MKV file as metadata using `mkvpropedit`.

## Error Handling

- If any files referenced in the CSV are missing or not found, the script will output an error and stop processing. You can review the list of missing files in the error message.
- If you provide an invalid option or fail to select a valid profile, the script will display an error message and exit.

## Exit Codes

- `0`: Success
- `1`: Error during file processing (e.g., missing files, invalid input)

## Contributing

If you would like to contribute or suggest improvements, please submit a pull request or open an issue.

---
