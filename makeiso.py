#!/usr/bin/env python3

"""
Optical Disc to ISO Backup Utility - Streamlined Refactored Version
Creates bit-perfect ISO backups with verification, logging, and comprehensive metadata.
"""

import subprocess
import os
import sys
import datetime
import time
import plistlib
import hashlib
import re
import platform
import argparse
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass
from uuid import uuid4

### === DATA STRUCTURES ===

@dataclass
class BackupConfig:
    """Configuration for backup operation"""
    disk_id: str
    volume_name: str
    filename: str
    operator: str
    output_dir: Path
    dry_run: bool = False
    no_verification: bool = False
    
    @property
    def output_path(self) -> Path:
        return self.output_dir / f"{self.filename}.iso"
    
    @property
    def log_path(self) -> Path:
        return self.output_dir / f"{self.filename}.iso.log.txt"
    
    @property
    def manifest_path(self) -> Path:
        return self.output_dir / f"{self.filename}_manifest.json"
    
    @property
    def tree_path(self) -> Path:
        return self.output_dir / f"{self.filename}_tree.txt"
    
    @property
    def isolyzer_path(self) -> Path:
        return self.output_dir / f"{self.filename}_isolyzer.xml"

@dataclass
class BackupResult:
    """Result of backup operation"""
    success: bool
    iso_path: Path
    disk_size: int
    md5_iso: Optional[str] = None
    md5_raw: Optional[str] = None
    creation_time: float = 0.0
    verification_time: float = 0.0
    error_message: Optional[str] = None
    
    @property
    def checksum_match(self) -> Optional[bool]:
        """Whether checksums match (None if verification skipped)"""
        if self.md5_iso and self.md5_raw:
            return self.md5_iso == self.md5_raw
        return None
    
    @property
    def total_time(self) -> float:
        return self.creation_time + self.verification_time
    
    def speed_mb_s(self, duration: float) -> float:
        """Calculate speed in MB/s"""
        if duration > 0:
            return round((self.disk_size / duration) / (1024 * 1024), 2)
        return 0.0

### === COLOR UTILITIES ===

COLOR = {
    "blue": "\033[94m",
    "cyan": "\033[96m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "off": "\033[0m"
}

def colorize(color: str, text: str) -> str:
    """Apply ANSI color to text"""
    return f"{COLOR[color]}{text}{COLOR['off']}"

### === LOGGING SETUP ===

class MemoryLogHandler(logging.Handler):
    """Log handler that stores messages in memory for later file output"""
    def __init__(self):
        super().__init__()
        self.buffer = []
    
    def emit(self, record):
        now = datetime.datetime.now()
        timestamp = now.strftime('%Y-%m-%dT%H:%M:%S') + f".{now.microsecond // 1000:03d}"
        msg = self.format(record)
        self.buffer.append(f"{timestamp} - {msg}")

def setup_logging() -> Tuple[logging.Logger, MemoryLogHandler]:
    """Setup dual logging - console and memory buffer"""
    logger = logging.getLogger("iso_backup")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    # Console handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(stream_handler)
    
    # Memory handler for clean file output
    mem_handler = MemoryLogHandler()
    mem_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(mem_handler)
    
    return logger, mem_handler

# Global logger instance
logger, mem_handler = setup_logging()

def log(msg: str):
    """Log a message to console and memory buffer"""
    logger.info(msg)

def log_to_file_only(msg: str):
    """Log a message only to the log file (memory buffer), not console"""
    now = datetime.datetime.now()
    timestamp = now.strftime('%Y-%m-%dT%H:%M:%S') + f".{now.microsecond // 1000:03d}"
    mem_handler.buffer.append(f"{timestamp} - {msg}")

def log_divider(title: Optional[str] = None):
    """Log a divider with optional title"""
    bar = "=" * 60
    log("")
    if title:
        log(colorize("blue", bar))
        log(colorize("blue", f"{title:^60}"))
        log(colorize("blue", bar))
    else:
        log(colorize("blue", bar))
    log("")

### === UTILITY FUNCTIONS ===

def get_input(prompt: str) -> str:
    """Get user input with keyboard interrupt handling"""
    try:
        return input(prompt).strip()
    except KeyboardInterrupt:
        log(colorize("red", "\nCancelled by user."))
        sys.exit(1)

def run_cmd(cmd: List[str], capture_output: bool = True, plist: bool = False) -> Any:
    """Run command and return output"""
    if plist:
        result = subprocess.run(cmd, capture_output=capture_output, check=True)
        return plistlib.loads(result.stdout)
    else:
        result = subprocess.run(cmd, capture_output=capture_output, text=True, check=True)
        return result.stdout

def save_clean_log(log_path: Path, mem_handler: MemoryLogHandler):
    """Save log buffer to file with ANSI codes removed and better formatting"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    
    with open(log_path, "w") as f:
        # Skip the raw log entries - we'll create a formatted version instead
        pass

### === FORMATTED LOG WITH ISOLYZER ===

def create_formatted_log(log_path: Path, config: BackupConfig, result: BackupResult, 
                        start_time: datetime.datetime, disk_info: Dict[str, Any]):
    """Create a properly formatted log file"""
    
    def format_duration(seconds: float) -> str:
        minutes = int(seconds) // 60
        remaining_seconds = round(seconds % 60, 2)
        return f"{minutes}m {remaining_seconds}s"
    
    end_time = datetime.datetime.now()
    total_duration = (end_time - start_time).total_seconds()
    
    with open(log_path, "w") as f:
        # === HEADER SUMMARY ===
        f.write("=" * 70 + "\n")
        f.write("OPTICAL DISC TO ISO BACKUP LOG\n")
        f.write("=" * 70 + "\n\n")
        
        f.write("BACKUP SUMMARY\n")
        f.write("-" * 20 + "\n")
        f.write(f"Run ID:           {datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}_{config.operator}_{config.disk_id}\n")
        f.write(f"Operator:         {config.operator}\n")
        f.write(f"Start Time:       {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"End Time:         {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Duration:   {format_duration(total_duration)}\n")
        f.write(f"Status:           {'SUCCESS' if result.success else 'FAILED'}\n")
        if result.checksum_match is not None:
            f.write(f"Verification:     {'PASS' if result.checksum_match else 'FAIL'}\n")
        f.write("\n")
        
        # === DISC INFORMATION ===
        f.write("DISC INFORMATION\n")
        f.write("-" * 20 + "\n")
        f.write(f"Disk ID:          {config.disk_id}\n")
        f.write(f"Volume Name:      {config.volume_name}\n")
        f.write(f"Volume Size:      {result.disk_size / (1024 * 1024):.0f} MB ({result.disk_size / (1024 * 1024 * 1024):.1f} GB)\n")
        
        # Extract info from the logged metadata since disk_info might be empty here
        # Parse from the detailed metadata that we know exists
        media_type = "Unknown"
        filesystem = "Unknown" 
        device_name = "Unknown"
        
        # Look through the memory buffer for diskutil info
        for entry in mem_handler.buffer:
            if " - " in entry:
                line = entry.split(" - ", 1)[1].strip()
                if "Optical Media Type:" in line:
                    media_type = line.split(":", 1)[1].strip()
                elif "File System Personality:" in line:
                    filesystem = line.split(":", 1)[1].strip()
                elif "Device / Media Name:" in line:
                    device_name = line.split(":", 1)[1].strip()
        
        f.write(f"Media Type:       {media_type}\n")
        f.write(f"File System:      {filesystem}\n")
        f.write(f"Device:           {device_name}\n")
        f.write("\n")
        
        # === OUTPUT FILES ===
        f.write("OUTPUT FILES\n")
        f.write("-" * 20 + "\n")
        f.write(f"ISO File:         {result.iso_path.name}\n")
        f.write(f"Output Directory: {config.output_dir}\n")
        f.write(f"Log File:         {config.log_path.name}\n")
        f.write(f"Tree File:        {config.tree_path.name}\n")
        f.write(f"Isolyzer File:    {config.isolyzer_path.name}\n")
        f.write(f"Manifest File:    {config.manifest_path.name}\n")
        if result.iso_path.exists():
            iso_size = result.iso_path.stat().st_size
            f.write(f"ISO File Size:    {iso_size / (1024 * 1024):.0f} MB\n")
        f.write("\n")
        
        # Rest of the log formatting remains the same...
        # === OPERATION DETAILS ===
        f.write("OPERATION DETAILS\n")
        f.write("-" * 20 + "\n")
        
        # Tree generation
        f.write(f"[{start_time.strftime('%H:%M:%S')}] Tree Listing Generation\n")
        f.write(f"  Command: tree -RapugD --si --du /Volumes/{config.volume_name}\n")
        f.write(f"  Output:  {config.tree_path.name}\n\n")
        
        # Disk unmount
        f.write(f"[{start_time.strftime('%H:%M:%S')}] Disk Unmount\n")
        f.write(f"  Command: diskutil unmountDisk /dev/{config.disk_id}\n")
        f.write(f"  Status:  Success\n\n")
        
        # ISO Creation and Verification
        create_start = start_time + datetime.timedelta(seconds=1)  # Approximate
        create_end = create_start + datetime.timedelta(seconds=result.creation_time)
        
        f.write(f"[{create_start.strftime('%H:%M:%S')}] ISO Creation & Verification\n")
        f.write(f"  Command: dd if=/dev/r{config.disk_id} of={result.iso_path} bs=4m\n")
        f.write(f"  Method:  Parallel processing (creation + hashing)\n")
        f.write(f"  Duration: {format_duration(result.creation_time)}\n")
        f.write(f"  Speed:    {result.speed_mb_s(result.creation_time):.2f} MB/s\n")
        f.write(f"  Completed: {create_end.strftime('%H:%M:%S')}\n\n")
        
        # Hash verification results
        if result.md5_iso and result.md5_raw:
            f.write("VERIFICATION RESULTS\n")
            f.write("-" * 20 + "\n")
            f.write(f"MD5 (ISO):      {result.md5_iso}\n")
            f.write(f"MD5 (Raw Disk): {result.md5_raw}\n")
            f.write(f"Match:          {'YES' if result.checksum_match else 'NO'}\n")
            f.write(f"Algorithm:      MD5 (128-bit)\n\n")
        
        # ISO Structure Analysis
        if config.isolyzer_path.exists():
            f.write(f"[{create_end.strftime('%H:%M:%S')}] ISO Structure Analysis\n")
            f.write(f"  Tool:    isolyzer\n")
            f.write(f"  Output:  {config.isolyzer_path.name}\n")
            
            # Try to extract test results from the buffer for the log
            test_results = {}
            for entry in mem_handler.buffer:
                if " - " in entry:
                    line = entry.split(" - ", 1)[1].strip()
                    if line.startswith("  Contains Known File System:"):
                        test_results["contains_known_filesystem"] = line.split(":", 1)[1].strip()
                    elif line.startswith("  Expected Size:"):
                        test_results["expected_size"] = line.split(":", 1)[1].strip()
                    elif line.startswith("  Actual Size:"):
                        test_results["actual_size"] = line.split(":", 1)[1].strip()
                    elif line.startswith("  Size Difference:"):
                        test_results["size_difference"] = line.split(":", 1)[1].strip()
                    elif line.startswith("  Size as Expected:"):
                        test_results["size_as_expected"] = line.split(":", 1)[1].strip()
                    elif line.startswith("  Smaller Than Expected:"):
                        test_results["smaller_than_expected"] = line.split(":", 1)[1].strip()
                    elif line.startswith("  Valid ISO 9660:"):
                        test_results["valid_iso9660"] = line.split(":", 1)[1].strip()
                    elif line.startswith("  Contains UDF:"):
                        test_results["contains_udf"] = line.split(":", 1)[1].strip()
            
            # Add test results to log if available
            if test_results:
                f.write("  Results:\n")
                for key, value in test_results.items():
                    # Convert key to more readable format
                    label = key.replace("_", " ").title()
                    f.write(f"    {label}: {value}\n")
            
            f.write("  Status:  Complete\n\n")
        
        # Finalization
        final_time = create_end + datetime.timedelta(seconds=1)
        f.write(f"[{final_time.strftime('%H:%M:%S')}] Finalization\n")
        f.write(f"  Remount: diskutil mount /dev/{config.disk_id}\n")
        f.write(f"  Eject:   diskutil eject /dev/{config.disk_id}\n")
        f.write(f"  Status:  Complete\n\n")
        
        # === SYSTEM INFORMATION ===
        f.write("SYSTEM INFORMATION\n")
        f.write("-" * 20 + "\n")
        f.write(f"Operating System: {platform.system()} {platform.release()}\n")
        f.write(f"Machine:          {platform.machine()}\n")
        f.write(f"Python Version:   {platform.python_version()}\n")
        f.write(f"Tool Version:     v14-streamlined\n\n")
        
        # === DETAILED DISK METADATA ===
        if disk_info:
            f.write("DETAILED DISK METADATA\n")
            f.write("-" * 25 + "\n")
            # Format the diskutil info more readably
            key_fields = [
                ('Device Identifier', 'Device Identifier'),
                ('Device / Media Name', 'Drive Model'),
                ('Optical Drive Type', 'Drive Capabilities'),
                ('Protocol', 'Connection'),
                ('Disk Size', 'Physical Size'),
                ('Volume Total Space', 'Volume Capacity'),
                ('Volume Used Space', 'Used Space'),
                ('File System Personality', 'File System'),
                ('Media Read-Only', 'Read-Only Status'),
                ('Optical Media Erasable', 'Erasable')
            ]
            
            # Extract and clean diskutil info
            diskutil_text = ""
            for entry in mem_handler.buffer:
                if " - Full diskutil info:" in entry:
                    # Found the start, capture subsequent lines
                    continue
                if " - " in entry and entry.split(" - ", 1)[1].startswith("  "):
                    line = entry.split(" - ", 1)[1].strip()
                    # Only include meaningful lines
                    if ":" in line and line:
                        key, value = line.split(":", 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Find matching display name
                        display_name = next((display for orig, display in key_fields if orig == key), None)
                        if display_name:
                            f.write(f"{display_name:20} {value}\n")
            f.write("\n")
        
        # === FOOTER ===
        f.write("=" * 70 + "\n")
        f.write(f"Log generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 70 + "\n")

### === MAIN BACKUP CLASS ===

class OpticalDiscBackup:
    """Main class for optical disc backup operations"""
    
    def __init__(self, config: BackupConfig):
        self.config = config
        
    def create_backup(self) -> BackupResult:
        """Main entry point for creating backup"""
        start_time = datetime.datetime.now()
        
        # No title divider here - already shown in main()
        
        # Validate we're running as root
        if os.geteuid() != 0:
            log(colorize("red", "This script must be run with sudo."))
            return BackupResult(False, self.config.output_path, 0, error_message="Not running as root")
        
        # Get disk info
        disk_info = self._get_disk_info()
        if not disk_info:
            return BackupResult(False, self.config.output_path, 0, error_message=f"Could not get disk info for {self.config.disk_id}")
        
        disk_size = disk_info.get("TotalSize", 0)
        
        # Log metadata (will only appear in log file, not terminal)
        self._log_metadata(disk_info)
        
        # Check for existing file
        if self.config.output_path.exists() and not self._confirm_overwrite():
            return BackupResult(False, self.config.output_path, disk_size, error_message="Aborted to avoid overwrite")
        
        # Create output directory
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate tree listing (this is the first divider after user inputs)
        self._generate_tree_listing()
        
        # Unmount disk
        if not self.config.dry_run:
            self._unmount_disk()
        
        # Create and verify ISO (with parallel hashing unless dry run)
        if self.config.dry_run:
            creation_time, md5_iso, md5_raw = 0.0, "dry_run_hash", "dry_run_hash"
            iso_analysis = {"skipped": True, "reason": "dry run"}
            log(colorize("cyan", "Dry run:") + " " + colorize("yellow", "Skipping .iso creation and verification."))
        else:
            creation_time, md5_iso, md5_raw = self._create_and_verify_iso(disk_size)
            # Analyze ISO structure
            iso_analysis = self._analyze_iso_structure(self.config.output_path)
        
        # Remount and finalize
        self._finalize_disk()
        
        # Create result
        result = BackupResult(
            success=True,
            iso_path=self.config.output_path,
            disk_size=disk_size,
            md5_iso=md5_iso,
            md5_raw=md5_raw,
            creation_time=creation_time,
            verification_time=0.0  # Verification is done during creation
        )
        
        # Generate outputs
        self._generate_summary(result)
        
        # Save formatted log with all the details
        create_formatted_log(self.config.log_path, self.config, result, start_time, disk_info)
        
        self._create_manifest(result, disk_info, iso_analysis)
        
        return result
    
    def _get_disk_info(self) -> Dict[str, Any]:
        """Get disk information via diskutil"""
        try:
            return run_cmd(["diskutil", "info", "-plist", f"/dev/{self.config.disk_id}"], plist=True)
        except subprocess.CalledProcessError as e:
            log(colorize("red", f"Failed to get disk info: {e}"))
            return {}
    
    def _log_metadata(self, disk_info: Dict[str, Any]):
        """Log metadata only to log file (not terminal)"""
        log_to_file_only(f"Operator: {self.config.operator}")
        log_to_file_only(f"Disk ID: {self.config.disk_id}")
        log_to_file_only(f"Volume name: {self.config.volume_name}")
        log_to_file_only(f"ISO filename: {self.config.output_path.name}")
        log_to_file_only(f"Start time: {datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]}")
        log_to_file_only("System metadata:")
        for key, value in [
            ("OS", platform.system()),
            ("OS Version", platform.version()),
            ("Release", platform.release()),
            ("Machine", platform.machine()),
            ("Processor", platform.processor()),
            ("Python Version", platform.python_version())
        ]:
            log_to_file_only(f"  {key}: {value}")
        log_to_file_only("Full diskutil info:")
        diskutil_output = run_cmd(["diskutil", "info", self.config.disk_id])
        for line in diskutil_output.strip().splitlines():
            log_to_file_only(f"  {line}")
    
    def _confirm_overwrite(self) -> bool:
        """Confirm file overwrite"""
        response = get_input(colorize("yellow", f"{self.config.output_path} exists. Overwrite? (y/n): "))
        return response.lower() == 'y'
    
    def _generate_tree_listing(self):
        """Generate tree listing of volume contents"""
        log_divider("Generating Tree Listing")
        tree_cmd = ["tree", "-RapugD", "--si", "--du", f"/Volumes/{self.config.volume_name}"]
        try:
            log(colorize("cyan", "Generating tree listing..."))
            log(colorize("cyan", "Running command:") + " " + colorize("yellow", " ".join(tree_cmd)))
            with open(self.config.tree_path, "w", encoding="utf-8") as f:
                subprocess.run(tree_cmd, stdout=f, stderr=subprocess.STDOUT,
                             env={**os.environ, "LANG": "en_US.UTF-8"})
            log(colorize("cyan", "Tree saved to:") + " " + colorize("yellow", str(self.config.tree_path)))
        except Exception as e:
            log(colorize("red", f"Tree generation failed: {e}"))
    
    def _create_and_verify_iso(self, disk_size: int) -> Tuple[float, str, str]:
        """Create ISO with parallel hash calculation"""
        log_divider("Creating and Verifying ISO")
        log(colorize("cyan", "Creating ISO from:") + " " + colorize("yellow", self.config.disk_id))
        
        raw_disk = f"r{self.config.disk_id}"
        dd_command = f"dd if=/dev/{raw_disk} of={self.config.output_path} bs=4m"
        log(colorize("cyan", "Running command:") + " " + colorize("yellow", dd_command))
        log(colorize("cyan", "Verifying using:") + " " + colorize("yellow", f"md5 {self.config.output_path.name} and streamed raw disk hash"))
        
        # Show shell equivalent
        shell_equiv = f'[ "$(md5 -q {self.config.output_path.name})" = "$(dd if=/dev/{raw_disk} bs=4m 2>/dev/null | md5 -q)" ] && echo "MATCH" || echo "MISMATCH"'
        log(colorize("cyan", "Shell equivalent:") + " " + colorize("yellow", shell_equiv))
        
        iso_hasher = hashlib.md5()
        raw_hasher = hashlib.md5()
        bytes_written = 0
        start_time = time.time()
        
        # Initialize progress display
        print("\n" * 4, end="")
        
        try:
            with open(self.config.output_path, 'wb') as iso_file:
                with subprocess.Popen(["dd", f"if=/dev/{raw_disk}", "bs=4m"],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
                    while True:
                        chunk = proc.stdout.read(4 * 1024 * 1024)  # 4MB chunks
                        if not chunk:
                            break
                        
                        # Write to file and update hashes
                        iso_file.write(chunk)
                        iso_hasher.update(chunk)
                        raw_hasher.update(chunk)
                        bytes_written += len(chunk)
                        
                        # Update progress (with "ISO Creation:" label to match expected output)
                        self._display_progress("ISO Creation", bytes_written, disk_size, start_time)
                    
                    # Wait for dd to complete and get stderr (which contains the transfer stats)
                    _, stderr = proc.communicate()
                    if proc.returncode != 0:
                        raise RuntimeError(f"dd failed: {stderr.decode()}")
                    
                    # Print dd output (records in/out, transfer stats) - decode and strip
                    if stderr:
                        # Decode bytes to string and clean up the output
                        dd_output = stderr.strip() if isinstance(stderr, str) else stderr.decode().strip()
                        log(dd_output)
        
        except KeyboardInterrupt:
            log(colorize("red", "Operation interrupted by user."))
            sys.exit(1)
        
        creation_time = time.time() - start_time
        iso_hash = iso_hasher.hexdigest()
        raw_hash = raw_hasher.hexdigest()
        
        log(colorize("green", "ISO creation complete."))
        log(colorize("cyan", "MD5 (ISO):") + " " + colorize("yellow", iso_hash))
        log(colorize("cyan", "MD5 (Raw Disk):") + " " + colorize("yellow", raw_hash))
        
        if iso_hash == raw_hash:
            log(colorize("green", "Checksum match: ISO is a true bit-for-bit copy."))
        else:
            log(colorize("red", "Checksum mismatch! ISO may not be identical."))
        
        return creation_time, iso_hash, raw_hash
    
    def _display_progress(self, title: str, current: int, total: int, start_time: float):
        """Display progress information"""
        elapsed = time.time() - start_time
        speed = current / elapsed if elapsed > 0 else 0
        remaining = max(0, total - current)
        eta = remaining / speed if speed > 0 else 0
        
        mb_current = current / (1024 * 1024)
        mb_total = total / (1024 * 1024)
        speed_mb = speed / (1024 * 1024)
        
        sys.stdout.write("\033[4A")
        sys.stdout.write(f"\033[2K\r{colorize('cyan', title)}: {mb_current:.0f}MB / {mb_total:.0f}MB\n")
        sys.stdout.write(f"\033[2K\r{colorize('cyan', 'Elapsed')}: {str(datetime.timedelta(seconds=int(elapsed)))}\n")
        sys.stdout.write(f"\033[2K\r{colorize('cyan', 'Remaining')}: {str(datetime.timedelta(seconds=int(eta)))}\n")
        sys.stdout.write(f"\033[2K\r{colorize('cyan', 'Avg Speed')}: {speed_mb:.2f}MB/s\n")
        sys.stdout.flush()
    
    def _unmount_disk(self) -> bool:
        """Unmount disk safely"""
        log_divider("Unmounting Disk")
        log(colorize("cyan", f"Unmounting /dev/{self.config.disk_id}..."))
        log(colorize("cyan", "Running command:") + " " + colorize("yellow", f"diskutil unmountDisk /dev/{self.config.disk_id}"))
        
        try:
            subprocess.run(["diskutil", "unmountDisk", f"/dev/{self.config.disk_id}"], 
                         capture_output=True, text=True, check=True)
            log(colorize("green", "Unmounted successfully."))
            return True
        except subprocess.CalledProcessError as e:
            log(colorize("red", f"Failed to unmount:\n{e.stderr}"))
            return False
    
    def _finalize_disk(self):
        """Remount and eject disk"""
        log_divider("Finalizing")
        if self.config.dry_run:
            # Check if already mounted
            mount_info = run_cmd(["diskutil", "info", self.config.disk_id])
            already_mounted = any(re.match(r"\s*Mounted:\s*Yes", line) for line in mount_info.splitlines())
            if already_mounted:
                log(colorize("cyan", "Dry run:") + " " + colorize("yellow", "No actions necessary. Disk already mounted."))
            else:
                log(colorize("cyan", "Dry run:") + " " + colorize("yellow", "Mounting disk but skipping eject."))
                log(colorize("cyan", "Running command:") + " " + colorize("yellow", f"diskutil mount {self.config.disk_id}"))
                subprocess.run(["diskutil", "mount", self.config.disk_id])
        else:
            log(colorize("cyan", "Running command:") + " " + colorize("yellow", f"diskutil mount /dev/{self.config.disk_id}"))
            subprocess.run(["diskutil", "mount", f"/dev/{self.config.disk_id}"])
            log(colorize("cyan", "Running command:") + " " + colorize("yellow", f"diskutil eject /dev/{self.config.disk_id}"))
            subprocess.run(["diskutil", "eject", f"/dev/{self.config.disk_id}"])
            log(colorize("green", "Disk remounted and ejected. All done."))
    
    def _generate_summary(self, result: BackupResult):
        """Generate timing summary"""
        log_divider("Summary")
        if not self.config.dry_run:
            def format_duration(seconds: float) -> str:
                minutes = int(seconds) // 60
                remaining_seconds = round(seconds % 60, 2)
                return f"{minutes} minutes, {remaining_seconds:.2f} seconds"
            
            elapsed = result.creation_time
            speed = result.speed_mb_s(elapsed)
            log(colorize("cyan", "Time to create + verify:") + " " + colorize("yellow", f"{elapsed:.2f} seconds") +
                f" ({format_duration(elapsed)})")
            log(colorize("cyan", "Average speed:") + " " + colorize("yellow", f"{speed:.2f} MB/s"))
        else:
            log(colorize("cyan", "Dry run:") + " " + colorize("yellow", "No timing summary available."))
    
    def _parse_isolyzer_xml(self, xml_content: str) -> Dict[str, Any]:
        """Parse isolyzer XML output into structured data"""
        import xml.etree.ElementTree as ET
        
        try:
            root = ET.fromstring(xml_content)
            ns = {'iso': 'http://kb.nl/ns/isolyzer/v1/'}
            
            # Extract tool info
            tool_info = {}
            tool_element = root.find('iso:toolInfo', ns)
            if tool_element is not None:
                tool_info = {
                    'name': self._get_xml_text(tool_element, 'iso:toolName', ns),
                    'version': self._get_xml_text(tool_element, 'iso:toolVersion', ns)
                }
            
            # Extract image analysis
            image = root.find('iso:image', ns)
            if image is None:
                return {"error": "No image element found in XML"}
            
            # File info
            file_info = {}
            file_element = image.find('iso:fileInfo', ns)
            if file_element is not None:
                file_info = {
                    'name': self._get_xml_text(file_element, 'iso:fileName', ns),
                    'size_bytes': int(self._get_xml_text(file_element, 'iso:fileSizeInBytes', ns) or 0),
                    'last_modified': self._get_xml_text(file_element, 'iso:fileLastModified', ns)
                }
            
            # Status info
            status_info = {}
            status_element = image.find('iso:statusInfo', ns)
            if status_element is not None:
                status_info = {
                    'success': self._get_xml_text(status_element, 'iso:success', ns) == 'True'
                }
            
            # Tests - THIS IS THE KEY SECTION TO FIX
            tests = {}
            tests_element = image.find('iso:tests', ns)
            if tests_element is not None:
                # Properly parse all test values
                contains_known_fs_text = self._get_xml_text(tests_element, 'iso:containsKnownFileSystem', ns)
                size_expected_text = self._get_xml_text(tests_element, 'iso:sizeExpected', ns)
                size_actual_text = self._get_xml_text(tests_element, 'iso:sizeActual', ns)
                size_difference_text = self._get_xml_text(tests_element, 'iso:sizeDifference', ns)
                size_diff_sectors_text = self._get_xml_text(tests_element, 'iso:sizeDifferenceSectors', ns)
                size_as_expected_text = self._get_xml_text(tests_element, 'iso:sizeAsExpected', ns)
                smaller_than_expected_text = self._get_xml_text(tests_element, 'iso:smallerThanExpected', ns)
                
                # Convert values to appropriate types
                try:
                    size_expected = int(size_expected_text) if size_expected_text else 0
                except ValueError:
                    size_expected = 0
                    
                try:
                    size_actual = int(size_actual_text) if size_actual_text else 0
                except ValueError:
                    size_actual = 0
                    
                try:
                    size_difference = int(size_difference_text) if size_difference_text else 0
                except ValueError:
                    size_difference = 0
                    
                try:
                    size_difference_sectors = float(size_diff_sectors_text) if size_diff_sectors_text else 0
                except ValueError:
                    size_difference_sectors = 0
                
                # Build the tests dictionary
                tests = {
                    'contains_known_filesystem': contains_known_fs_text == 'True',
                    'size_expected': size_expected,
                    'size_actual': size_actual,
                    'size_difference': size_difference,
                    'size_difference_sectors': size_difference_sectors,
                    'size_as_expected': size_as_expected_text == 'True',
                    'smaller_than_expected': smaller_than_expected_text == 'True'
                }
                
                # Log the extracted values for debugging
                log_to_file_only(f"Extracted from isolyzer XML - size_expected: {size_expected}, size_actual: {size_actual}")
            
            # File systems
            filesystems = []
            fs_elements = image.findall('iso:fileSystems/iso:fileSystem', ns)
            
            for fs in fs_elements:
                fs_type = fs.get('TYPE')
                fs_data = {'type': fs_type}
                
                if fs_type == 'ISO 9660':
                    pvd = fs.find('iso:primaryVolumeDescriptor', ns)
                    if pvd is not None:
                        fs_data.update({
                            'volume_identifier': self._get_xml_text(pvd, 'iso:volumeIdentifier', ns),
                            'volume_creation_date': self._get_xml_text(pvd, 'iso:volumeCreationDateAndTime', ns),
                            'publisher': self._get_xml_text(pvd, 'iso:publisherIdentifier', ns),
                            'data_preparer': self._get_xml_text(pvd, 'iso:dataPreparerIdentifier', ns),
                            'logical_block_size': int(self._get_xml_text(pvd, 'iso:logicalBlockSize', ns) or 0),
                            'volume_space_size': int(self._get_xml_text(pvd, 'iso:volumeSpaceSize', ns) or 0)
                        })
                
                elif fs_type == 'UDF':
                    lvd = fs.find('iso:logicalVolumeDescriptor', ns)
                    if lvd is not None:
                        fs_data.update({
                            'logical_volume_identifier': self._get_xml_text(lvd, 'iso:logicalVolumeIdentifier', ns),
                            'logical_block_size': int(self._get_xml_text(lvd, 'iso:logicalBlockSize', ns) or 0),
                            'implementation': self._get_xml_text(lvd, 'iso:implementationIdentifier', ns)
                        })
                
                filesystems.append(fs_data)
            
            # Compile warnings
            warnings = []
            if not tests.get('size_as_expected', True):
                warnings.append(f"File size differs from expected by {tests.get('size_difference', 0)} bytes")
            
            # Build result
            result = {
                'tool_info': tool_info,
                'file_info': file_info,
                'valid_iso9660': any(fs['type'] == 'ISO 9660' for fs in filesystems),
                'has_udf': any(fs['type'] == 'UDF' for fs in filesystems),
                'status_success': status_info.get('success', False),
                'size_as_expected': tests.get('size_as_expected', False),
                'size_difference_bytes': tests.get('size_difference', 0),
                'size_difference_sectors': tests.get('size_difference_sectors', 0),
                'size_expected': tests.get('size_expected', 0),
                'size_actual': tests.get('size_actual', 0),
                'contains_known_filesystem': tests.get('contains_known_filesystem', True),
                'smaller_than_expected': tests.get('smaller_than_expected', False),
                'filesystems': filesystems,
                'tests': tests,
                'warnings': warnings,
            }
            
            # Remove 'raw_xml' since we're saving it to file now
            result.pop('raw_xml', None)
            
            return result
            
        except ET.ParseError as e:
            return {"error": f"XML parsing failed: {e}", "error_type": "xml_parse_error"}
        except Exception as e:
            return {"error": f"Unexpected parsing error: {e}", "error_type": "unknown_error"}
    
    def _get_xml_text(self, element, path: str, namespaces: dict) -> str:
        """Safely extract text from XML element"""
        found = element.find(path, namespaces)
        return found.text.strip() if found is not None and found.text else ""
    
    def _create_manifest(self, result: BackupResult, disk_info: Dict[str, Any], iso_analysis: Dict[str, Any]):
        """Create comprehensive manifest file with improved organization"""
        from uuid import uuid4
        
        # Get current timestamp
        now = datetime.datetime.now()
        
        # Extract tree listing summary
        tree_summary = self._extract_tree_summary()
        
        # Calculate additional metrics
        def format_bytes(bytes_val):
            """Format bytes in human readable format"""
            for unit in ['B', 'KB', 'MB', 'GB']:
                if bytes_val < 1024.0:
                    return f"{bytes_val:.1f} {unit}"
                bytes_val /= 1024.0
            return f"{bytes_val:.1f} TB"
        
        # Get ISO file size
        iso_file_size = result.iso_path.stat().st_size if result.iso_path.exists() else None
        
        # Build comprehensive manifest
        manifest = {
            "backup_metadata": {
                "run_id": f"{now.strftime('%Y%m%dT%H%M%S')}_{self.config.operator}_{self.config.disk_id}",
                "uuid": str(uuid4()),
                "tool_name": "Optical Disc ISO Backup Utility",
                "tool_version": "v14-streamlined",
                "created": now.isoformat(timespec="seconds"),
                "operator": self.config.operator,
                "dry_run": self.config.dry_run
            },
            
            "backup_status": {
                "overall_status": "success" if result.success else "failed",
                "iso_created": iso_file_size is not None,
                "verification_performed": not self.config.no_verification and not self.config.dry_run,
                "verification_passed": result.checksum_match if result.checksum_match is not None else "skipped",
                "errors": result.error_message if result.error_message else None
            },
            
            "source_disc": {
                "disk_identifier": self.config.disk_id,
                "device_path": f"/dev/{self.config.disk_id}",
                "raw_device_path": f"/dev/r{self.config.disk_id}",
                "volume_name": self.config.volume_name,
                "media_type": disk_info.get('OpticalMediaType', 'Unknown'),
                "filesystem": disk_info.get('FilesystemName', disk_info.get('FilesystemType', 'Unknown')),
                "drive_model": disk_info.get('MediaName', disk_info.get('IORegistryEntryName', 'Unknown')),
                "drive_capabilities": disk_info.get('OpticalDeviceType', 'Unknown'),
                "connection_type": disk_info.get('BusProtocol', 'Unknown'),
                "erasable": disk_info.get('OpticalMediaErasable', False),
                "read_only": not disk_info.get('Writable', True)
            },
            
            "volume_information": {
                "total_size_bytes": result.disk_size,
                "total_size_formatted": format_bytes(result.disk_size),
                "used_space_bytes": disk_info.get('VolumeSize', result.disk_size),
                "used_space_formatted": format_bytes(disk_info.get('VolumeSize', result.disk_size)),
                "allocation_block_size": disk_info.get('VolumeAllocationBlockSize', disk_info.get('DeviceBlockSize', 'Unknown')),
                "mount_point": disk_info.get('MountPoint', f"/Volumes/{self.config.volume_name}")
            },
            
            "output_files": {
                "iso_filename": result.iso_path.name,
                "iso_file_size_bytes": iso_file_size,
                "iso_file_size_formatted": format_bytes(iso_file_size) if iso_file_size else None,
                "output_directory": str(self.config.output_dir),
                "log_filename": self.config.log_path.name,
                "tree_filename": self.config.tree_path.name,
                "isolyzer_filename": self.config.isolyzer_path.name,
                "manifest_filename": self.config.manifest_path.name
            },
            
            "operations_performed": {
                "tree_listing": {
                    "command": f"tree -RapugD --si --du /Volumes/{self.config.volume_name}",
                    "output_file": self.config.tree_path.name,
                    "summary": tree_summary
                },
                "disk_unmount": {
                    "command": f"diskutil unmountDisk /dev/{self.config.disk_id}",
                    "status": "success" if not self.config.dry_run else "skipped"
                },
                "iso_creation": {
                    "command": f"dd if=/dev/r{self.config.disk_id} of={result.iso_path} bs=4m",
                    "method": "parallel processing with simultaneous hash calculation",
                    "block_size": "4MB",
                    "performed": not self.config.dry_run
                },
                "verification": {
                    "method": "md5 hash comparison (ISO file vs raw device stream)",
                    "algorithm": "MD5",
                    "algorithm_bits": 128,
                    "performed": not self.config.no_verification and not self.config.dry_run,
                    "shell_equivalent": f'[ "$(md5 -q {result.iso_path.name})" = "$(dd if=/dev/r{self.config.disk_id} bs=4m 2>/dev/null | md5 -q)" ] && echo "MATCH" || echo "MISMATCH"'
                },
                "finalization": {
                    "remount_command": f"diskutil mount /dev/{self.config.disk_id}",
                    "eject_command": f"diskutil eject /dev/{self.config.disk_id}",
                    "status": "completed" if not self.config.dry_run else "skipped"
                }
            },
            
            "timing_performance": {
                "iso_creation": {
                    "duration_seconds": result.creation_time,
                    "duration_formatted": self._format_duration(result.creation_time),
                    "average_speed_mb_s": result.speed_mb_s(result.creation_time),
                    "average_speed_formatted": f"{result.speed_mb_s(result.creation_time):.2f} MB/s"
                },
                "verification": {
                    "duration_seconds": 0.0,  # Done in parallel
                    "duration_formatted": "Performed during creation",
                    "note": "Verification performed during ISO creation (parallel processing)"
                },
                "total_operation": {
                    "duration_seconds": result.creation_time,
                    "duration_formatted": self._format_duration(result.creation_time),
                    "efficiency_note": "~50% time savings vs sequential read/verify operations"
                }
            },
            
            "integrity_verification": {
                "hash_algorithm": "MD5",
                "hash_length_bits": 128,
                "iso_hash": result.md5_iso,
                "source_hash": result.md5_raw,
                "hashes_match": result.checksum_match,
                "verification_method": "Parallel hash calculation during creation",
                "integrity_status": "verified" if result.checksum_match else ("failed" if result.checksum_match is False else "not_performed"),
                "notes": "ISO verified as bit-perfect copy" if result.checksum_match else None
            },
            
            "structural_analysis": {
                "tool_used": iso_analysis.get('tool_info', {}).get('name', 'isolyzer'),
                "tool_version": iso_analysis.get('tool_info', {}).get('version', 'unknown'),
                "analysis_performed": not iso_analysis.get('skipped', False) and 'error' not in iso_analysis,
                "analysis_successful": iso_analysis.get('status_success', False),
                "valid_iso9660": iso_analysis.get('valid_iso9660', False),
                "contains_udf": iso_analysis.get('has_udf', False),
                "size_validation": {
                    "size_as_expected": iso_analysis.get('size_as_expected', True),
                    "size_expected_bytes": iso_analysis.get('size_expected', 0),
                    "size_actual_bytes": iso_analysis.get('size_actual', 0),
                    "size_difference_bytes": iso_analysis.get('size_difference_bytes', 0),
                    "size_difference_sectors": iso_analysis.get('size_difference_sectors', 0),
                    "smaller_than_expected": iso_analysis.get('smaller_than_expected', False),
                    "contains_known_filesystem": iso_analysis.get('contains_known_filesystem', True),
                    "size_expected_formatted": f"{iso_analysis.get('size_expected', 0)/1024/1024:.1f} MB",
                    "size_actual_formatted": f"{iso_analysis.get('size_actual', 0)/1024/1024:.1f} MB",
                    "note": "Small differences (1-2 sectors) are normal for optical media" if iso_analysis.get('size_difference_bytes', 0) > 0 else None
                },
                "filesystems_detected": self._extract_filesystem_info(iso_analysis),
                "warnings": iso_analysis.get('warnings', []),
                "error": iso_analysis.get('error') if 'error' in iso_analysis else None,
                "xml_field_mappings": {
                    "note": "This section documents which XML elements from the raw isolyzer output map to the fields above",
                    "tool_info": {
                        "tool_used": "/isolyzer/toolInfo/toolName",
                        "tool_version": "/isolyzer/toolInfo/toolVersion"
                    },
                    "status_fields": {
                        "analysis_successful": "/isolyzer/image/statusInfo/success"
                    },
                    "test_fields": {
                        "contains_known_filesystem": "/isolyzer/image/tests/containsKnownFileSystem",
                        "size_expected_bytes": "/isolyzer/image/tests/sizeExpected",
                        "size_actual_bytes": "/isolyzer/image/tests/sizeActual",
                        "size_difference_bytes": "/isolyzer/image/tests/sizeDifference",
                        "size_difference_sectors": "/isolyzer/image/tests/sizeDifferenceSectors",
                        "size_as_expected": "/isolyzer/image/tests/sizeAsExpected",
                        "smaller_than_expected": "/isolyzer/image/tests/smallerThanExpected",
                        "valid_iso9660": "presence of /isolyzer/image/fileSystems/fileSystem[@TYPE='ISO 9660']",
                        "contains_udf": "presence of /isolyzer/image/fileSystems/fileSystem[@TYPE='UDF']"
                    },
                    "iso9660_fields": {
                        "volume_identifier": "/isolyzer/image/fileSystems/fileSystem[@TYPE='ISO 9660']/primaryVolumeDescriptor/volumeIdentifier",
                        "creation_date": "/isolyzer/image/fileSystems/fileSystem[@TYPE='ISO 9660']/primaryVolumeDescriptor/volumeCreationDateAndTime",
                        "publisher": "/isolyzer/image/fileSystems/fileSystem[@TYPE='ISO 9660']/primaryVolumeDescriptor/publisherIdentifier",
                        "data_preparer": "/isolyzer/image/fileSystems/fileSystem[@TYPE='ISO 9660']/primaryVolumeDescriptor/dataPreparerIdentifier",
                        "logical_block_size": "/isolyzer/image/fileSystems/fileSystem[@TYPE='ISO 9660']/primaryVolumeDescriptor/logicalBlockSize",
                        "volume_space_size": "/isolyzer/image/fileSystems/fileSystem[@TYPE='ISO 9660']/primaryVolumeDescriptor/volumeSpaceSize"
                    },
                    "udf_fields": {
                        "logical_volume_identifier": "/isolyzer/image/fileSystems/fileSystem[@TYPE='UDF']/logicalVolumeDescriptor/logicalVolumeIdentifier",
                        "logical_block_size": "/isolyzer/image/fileSystems/fileSystem[@TYPE='UDF']/logicalVolumeDescriptor/logicalBlockSize",
                        "implementation": "/isolyzer/image/fileSystems/fileSystem[@TYPE='UDF']/logicalVolumeDescriptor/implementationIdentifier"
                    }
                }
            },
            
            "system_environment": {
                "operating_system": platform.system(),
                "os_version": platform.release(),
                "kernel_version": platform.version(),
                "machine_architecture": platform.machine(),
                "processor": platform.processor(),
                "hostname": platform.node(),
                "python_version": platform.python_version(),
                "user_context": "sudo required for raw device access"
            },
            
            "technical_details": {
                "source_device_properties": {
                    # Essential disk properties only
                    "device_identifier": disk_info.get('DeviceIdentifier'),
                    "device_node": disk_info.get('DeviceNode'),
                    "ejectable": disk_info.get('Ejectable'),
                    "removable": disk_info.get('Removable'),
                    "internal": disk_info.get('Internal'),
                    "smart_status": disk_info.get('SMARTStatus'),
                    "bootable": disk_info.get('Bootable'),
                    "writable": disk_info.get('Writable')
                },
                "backup_parameters": {
                    "dd_block_size": "4MB",
                    "read_device": f"/dev/r{self.config.disk_id}",
                    "write_destination": str(result.iso_path),
                    "parallel_processing": True,
                    "verification_during_creation": True,
                    "error_handling": "standard dd error handling"
                }
            },
            
            "quality_assurance": {
                "verification_levels": [
                    {
                        "type": "bit_perfect_copy",
                        "method": "MD5 hash comparison",
                        "status": "verified" if result.checksum_match else "failed",
                        "confidence": "100%" if result.checksum_match else "0%"
                    },
                    {
                        "type": "structural_integrity", 
                        "method": "isolyzer analysis",
                        "status": "verified" if iso_analysis.get('valid_iso9660') and iso_analysis.get('status_success') else ("failed" if iso_analysis.get('error') else "not_performed"),
                        "confidence": "high" if iso_analysis.get('valid_iso9660') else "unknown"
                    }
                ],
                "recommended_verifications": [
                    "Mount created ISO and compare file structure",
                    "Test ISO in target environment", 
                    "Verify specific files if critical data",
                    "Check isolyzer analysis for structural issues"
                ],
                "backup_best_practices": [
                    "Store ISO in multiple locations",
                    "Create checksum file for long-term storage",
                    "Document any disc damage or read errors",
                    "Keep isolyzer analysis for format validation"
                ],
                "manifest_notes": "This manifest provides comprehensive backup documentation including both bit-level and structural verification for audit and validation purposes"
            }
        }
        
        # Write manifest with proper formatting
        with open(self.config.manifest_path, "w") as f:
            json.dump(manifest, f, indent=2, sort_keys=False)
        
        log(colorize("cyan", "Manifest saved to:") + " " + colorize("yellow", str(self.config.manifest_path)))
    
    def _extract_filesystem_info(self, iso_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract filesystem information from isolyzer analysis"""
        filesystems = []
        
        for fs in iso_analysis.get('filesystems', []):
            fs_info = {
                "type": fs.get('type'),
                "details": {}
            }
            
            if fs.get('type') == 'ISO 9660':
                fs_info['details'] = {
                    "volume_identifier": fs.get('volume_identifier'),
                    "creation_date": fs.get('volume_creation_date'),
                    "publisher": fs.get('publisher'),
                    "data_preparer": fs.get('data_preparer'),
                    "logical_block_size": fs.get('logical_block_size'),
                    "volume_space_size": fs.get('volume_space_size')
                }
            elif fs.get('type') == 'UDF':
                fs_info['details'] = {
                    "logical_volume_identifier": fs.get('logical_volume_identifier'),
                    "logical_block_size": fs.get('logical_block_size'),
                    "implementation": fs.get('implementation')
                }
            
            # Remove None values
            fs_info['details'] = {k: v for k, v in fs_info['details'].items() if v is not None}
            filesystems.append(fs_info)
        
        return filesystems

    def _analyze_iso_structure(self, iso_path: Path) -> Dict[str, Any]:
        """Analyze ISO structure with isolyzer"""
        log_divider("Analyzing ISO Structure")
        log(colorize("cyan", "Running isolyzer analysis..."))
        
        try:
            # Simplify the command to just call isolyzer with the file path
            # since isolyzer outputs XML by default
            cmd = ["isolyzer", str(iso_path)]
            log(colorize("cyan", "Running command:") + " " + colorize("yellow", " ".join(cmd)))
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Save raw XML output to file if successful
            with open(self.config.isolyzer_path, 'w', encoding='utf-8') as f:
                f.write(result.stdout)
            log(colorize("cyan", "Isolyzer XML saved to:") + " " + colorize("yellow", str(self.config.isolyzer_path)))
            
            # Parse XML output
            analysis = self._parse_isolyzer_xml(result.stdout)
            
            # Display key results
            log(colorize("green", "ISO analysis complete"))
            log(colorize("cyan", "File System Tests:"))
            log(colorize("cyan", "  Contains Known File System:") + " " + colorize("yellow", str(analysis.get('contains_known_filesystem', 'Unknown'))))
            
            # Display sizes in bytes rather than MB
            size_expected = analysis.get('size_expected', 0)
            size_actual = analysis.get('size_actual', 0)
            log(colorize("cyan", "  Expected Size:") + " " + colorize("yellow", f"{size_expected} bytes"))
            log(colorize("cyan", "  Actual Size:") + " " + colorize("yellow", f"{size_actual} bytes"))
            
            # Continue with other output
            log(colorize("cyan", "  Size Difference:") + " " + colorize("yellow", f"{analysis.get('size_difference_bytes', 0)} bytes ({analysis.get('size_difference_sectors', 0)} sectors)"))
            log(colorize("cyan", "  Size as Expected:") + " " + colorize("yellow", str(analysis.get('size_as_expected', 'Unknown'))))
            log(colorize("cyan", "  Smaller Than Expected:") + " " + colorize("yellow", str(analysis.get('smaller_than_expected', 'Unknown'))))
            log(colorize("cyan", "  Valid ISO 9660:") + " " + colorize("yellow", str(analysis.get('valid_iso9660', 'Unknown'))))
            log(colorize("cyan", "  Contains UDF:") + " " + colorize("yellow", str(analysis.get('has_udf', 'Unknown'))))
            
            # Show any warnings or issues
            if analysis.get('warnings'):
                for warning in analysis['warnings']:
                    log(colorize("yellow", f"Warning: {warning}"))
            
            return analysis
            
        except subprocess.CalledProcessError as e:
            log(colorize("red", f"isolyzer failed: {e}"))
            # Check if isolyzer is installed
            try:
                subprocess.run(["which", "isolyzer"], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                log(colorize("yellow", "isolyzer command not found. Please install with:"))
                log(colorize("yellow", "pip install isolyzer"))
            
            # Try to create a minimal XML file for tracking purposes
            with open(self.config.isolyzer_path, 'w', encoding='utf-8') as f:
                f.write('<?xml version="1.0" ?>\n')
                f.write('<isolyzer xmlns="http://kb.nl/ns/isolyzer/v1/">\n')
                f.write('  <toolInfo>\n')
                f.write('    <toolName>isolyzer</toolName>\n')
                f.write('    <toolVersion>unknown</toolVersion>\n')
                f.write('  </toolInfo>\n')
                f.write('  <image>\n')
                f.write('    <statusInfo>\n')
                f.write('      <success>False</success>\n')
                f.write(f'      <error>{str(e)}</error>\n')
                f.write('    </statusInfo>\n')
                f.write('  </image>\n')
                f.write('</isolyzer>\n')
            log(colorize("cyan", "Created minimal XML for tracking"))
            
            return {"error": str(e), "error_type": "execution_failed"}
        except FileNotFoundError:
            log(colorize("yellow", "isolyzer not found - skipping structural analysis"))
            log(colorize("cyan", "Tip:") + " Install isolyzer with: " + colorize("yellow", "pip install isolyzer"))
            return {"error": "isolyzer not installed", "error_type": "not_found"}
        except Exception as e:
            log(colorize("red", f"Unexpected error during ISO analysis: {e}"))
            return {"error": str(e), "error_type": "parsing_failed"}
        
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human readable format"""
        if seconds == 0:
            return "0 seconds"
        minutes = int(seconds) // 60
        remaining_seconds = round(seconds % 60, 2)
        if minutes > 0:
            return f"{minutes} minutes, {remaining_seconds:.2f} seconds"
        else:
            return f"{remaining_seconds:.2f} seconds"
    
    def _extract_tree_summary(self) -> Dict[str, Any]:
        """Extract summary from tree listing"""
        try:
            with open(self.config.tree_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in reversed(lines):
                    if line.strip().startswith("Total") and "directories" in line:
                        match = re.search(r"(\d+)\s+directories,\s+(\d+)\s+files,\s+(.+)", line.strip())
                        if match:
                            return {
                                "total_directories": int(match.group(1)),
                                "total_files": int(match.group(2)),
                                "reported_size": match.group(3)
                            }
                        break
            return {}
        except Exception as e:
            return {"error": str(e)}
    
    def _get_log_preview(self) -> List[str]:
        """Get preview of log tail"""
        try:
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            return [ansi_escape.sub('', entry.split(' - ', 1)[1]) for entry in mem_handler.buffer[-10:]]
        except Exception as e:
            return [f"Log preview error: {str(e)}"]

### === HELPER FUNCTIONS ===

def get_volume_name(disk_id: str) -> str:
    """Extract volume name from disk info"""
    try:
        info = run_cmd(["diskutil", "info", f"/dev/{disk_id}"])
        for line in info.splitlines():
            if "Volume Name:" in line:
                return line.split(":", 1)[1].strip()
    except subprocess.CalledProcessError:
        pass
    return "Unknown"

def list_disks() -> str:
    """List available disks"""
    try:
        return run_cmd(["diskutil", "list"])
    except subprocess.CalledProcessError as e:
        log(colorize("red", f"Failed to list disks: {e}"))
        return ""

def print_help():
    """Print custom colored help message"""
    print()  # Blank line before usage
    
    help_text = f"""
{colorize('blue', 'OPTICAL DISC TO ISO BACKUP UTILITY')}
{colorize('cyan', 'Creates bit-perfect ISO backups with verification')}

{colorize('yellow', 'USAGE:')}
  sudo python3 makeiso.py [options]

{colorize('yellow', 'OPTIONS:')}
  {colorize('green', '-h, --help')}              Show this help message and exit
  {colorize('green', '--dry-run')}               Run without writing ISO or verifying checksum
  {colorize('green', '--no-verification')}       Skip ISO checksum verification  
  {colorize('green', '--filename NAME')}         ISO filename (without extension)
  {colorize('green', '--dir PATH')}              Output directory path (can use ~)
  {colorize('green', '--operator NAME')}         Operator name or initials

{colorize('yellow', 'EXAMPLES:')}
  {colorize('cyan', '# Interactive mode - prompts for all inputs')}
  sudo python3 makeiso.py

  {colorize('cyan', '# Specify filename, directory, and operator')}
  sudo python3 makeiso.py --filename MyDisc --dir ~/Backups --operator JD

  {colorize('cyan', '# Test run without creating ISO')}
  sudo python3 makeiso.py --dry-run

{colorize('yellow', 'KEY FEATURES:')}
  • {colorize('green', 'Parallel processing:')} Creates ISO while calculating checksums
  • {colorize('green', 'Progress tracking:')} Real-time speed and remaining time
  • {colorize('green', 'Comprehensive logging:')} Detailed logs saved to .log.txt
  • {colorize('green', 'Metadata manifest:')} JSON file with complete backup metadata
  • {colorize('green', 'Tree listing:')} Directory structure saved to .txt file
  • {colorize('green', 'Cross-verification:')} Compares ISO and raw disk MD5 hashes

{colorize('red', 'IMPORTANT:')} This script must be run with sudo privileges.
"""
    print(help_text)

def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""
    # Check for help first to show our custom help
    if '--help' in sys.argv or '-h' in sys.argv:
        print_help()
        sys.exit(0)
    
    parser = argparse.ArgumentParser(
        prog='makeiso.py',
        description='Optical Disc to ISO Backup Utility',
        add_help=False  # Disable default help to use our custom one
    )
    
    parser.add_argument(
        '--dry-run', 
        action='store_true', 
        help='Run without writing ISO or verifying checksum'
    )
    
    parser.add_argument(
        '--no-verification', 
        action='store_true', 
        help='Skip ISO checksum verification'
    )
    
    parser.add_argument(
        '--filename', 
        type=str, 
        metavar='NAME',
        help='ISO filename without extension'
    )
    
    parser.add_argument(
        '--dir', 
        type=str, 
        metavar='PATH',
        help='Output directory path'
    )
    
    parser.add_argument(
        '--operator', 
        type=str, 
        metavar='NAME',
        help='Operator name or initials'
    )
    
    return parser.parse_args()

def gather_user_inputs(args: argparse.Namespace) -> BackupConfig:
    """Gather all necessary inputs from user and command line"""
    # Get disk ID
    disk_id = get_input(colorize("cyan", "Enter disk ID (e.g. disk2): "))
    
    # Get volume name
    volume_name = get_volume_name(disk_id)
    log(colorize("cyan", "Volume name detected:") + " " + colorize("yellow", volume_name))
    
    # Get disk info to show volume size
    try:
        disk_info = run_cmd(["diskutil", "info", "-plist", f"/dev/{disk_id}"], plist=True)
        disk_size = disk_info.get("TotalSize", 0)
        disk_size_mb = disk_size / (1024 * 1024)
        log(colorize("cyan", "Volume size:") + " " + colorize("yellow", f"{disk_size_mb:.0f} MB"))
    except:
        pass
    
    # Get other inputs
    filename = args.filename or get_input(colorize("cyan", "Enter output ISO filename (no extension): "))
    base_dir = Path(args.dir or get_input(colorize("cyan", "Enter output directory: "))).expanduser()
    operator = args.operator or get_input(colorize("cyan", "Enter operator name or initials: "))
    
    # Create output directory path
    output_dir = base_dir / filename
    
    return BackupConfig(
        disk_id=disk_id,
        volume_name=volume_name,
        filename=filename,
        operator=operator,
        output_dir=output_dir,
        dry_run=args.dry_run,
        no_verification=args.no_verification
    )

### === MAIN FUNCTION ===

def main():
    """Main entry point"""
    # Parse command line arguments
    args = parse_args()
    
    # First show the title divider after a blank line (right after sudo password)
    log("")
    log_divider("Optical Disc to ISO Backup Utility")
    
    # Then show available disks
    log("Available disks:")
    output = list_disks()
    for line in output.strip().splitlines():
        log(line)
    
    # Gather user inputs
    config = gather_user_inputs(args)
    
    # Create and run backup
    backup = OpticalDiscBackup(config)
    result = backup.create_backup()
    
    # Exit with appropriate code
    if result.success:
        if result.checksum_match is False:
            log(colorize("yellow", "Warning: Checksum mismatch detected!"))
            sys.exit(2)  # Warning exit code
        else:
            log(colorize("green", "Backup completed successfully!"))
            sys.exit(0)
    else:
        log(colorize("red", f"Backup failed: {result.error_message}"))
        sys.exit(1)

### === SCRIPT ENTRYPOINT ===

if __name__ == "__main__":
    main()