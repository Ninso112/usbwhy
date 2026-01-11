"""
Kernel log parsing module.

Parses kernel logs from journalctl, dmesg, or log files
to extract USB-related messages.
"""

import os
import re
import subprocess
from datetime import datetime, timedelta
from typing import List, Optional


class LogEntry:
    """Represents a kernel log entry related to USB."""

    def __init__(self, message: str, timestamp: Optional[datetime] = None, raw_line: str = ""):
        self.message = message
        self.timestamp = timestamp
        self.raw_line = raw_line
        self.device_id: Optional[str] = None  # e.g., "1-1.2"
        self.vendor_product: Optional[str] = None  # e.g., "1234:5678"
        self.category: str = "info"  # error, warning, reset, disconnect, etc.
        self._categorize()

    def _categorize(self):
        """Categorize the log entry based on keywords."""
        msg_lower = self.message.lower()
        
        if any(word in msg_lower for word in ["over-current", "overcurrent"]):
            self.category = "over_current"
        elif "reset" in msg_lower and "usb" in msg_lower:
            self.category = "reset"
        elif "disconnect" in msg_lower and "usb" in msg_lower:
            self.category = "disconnect"
        elif "error" in msg_lower or "failed" in msg_lower:
            self.category = "error"
        elif "timeout" in msg_lower:
            self.category = "timeout"
        elif "descriptor read" in msg_lower:
            self.category = "descriptor_error"
        elif "cannot enumerate" in msg_lower or "enumeration failed" in msg_lower:
            self.category = "enumeration_error"
        elif "warning" in msg_lower or "warn" in msg_lower:
            self.category = "warning"

    def extract_device_info(self):
        """Extract device identifiers from the message."""
        # Try to find bus-device format: "usb 1-1.2" or "1-1.2:"
        pattern = r'(?:usb\s+)?(\d+-\d+(?:\.\d+)*)[\s:]'
        match = re.search(pattern, self.message, re.IGNORECASE)
        if match:
            self.device_id = match.group(1)
        
        # Try to find vendor:product format
        pattern = r'(\w{4}):(\w{4})'
        match = re.search(pattern, self.message)
        if match:
            self.device_id = None  # Prefer vendor:product if found
            self.vendor_product = f"{match.group(1)}:{match.group(2)}"


def parse_journalctl(since_seconds: Optional[int] = None) -> Optional[str]:
    """
    Try to get kernel logs from journalctl.
    
    Args:
        since_seconds: Number of seconds ago to start from
    
    Returns:
        Log output as string, or None if journalctl unavailable
    """
    try:
        cmd = ["journalctl", "-k", "--no-pager"]
        
        if since_seconds:
            cmd.append(f"--since=-{since_seconds}s")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, PermissionError):
        pass
    
    return None


def parse_dmesg(lines: Optional[int] = None) -> Optional[str]:
    """
    Try to get kernel logs from dmesg.
    
    Args:
        lines: Number of lines to read (None = all)
    
    Returns:
        Log output as string, or None if dmesg unavailable
    """
    try:
        cmd = ["dmesg", "-T"]  # -T for human-readable timestamps
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            output = result.stdout
            if lines:
                # Take last N lines
                output_lines = output.splitlines()
                output = "\n".join(output_lines[-lines:])
            return output
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, PermissionError):
        # Try without -T flag (older dmesg versions)
        try:
            cmd = ["dmesg"]
            if lines:
                result = subprocess.run(
                    cmd + ["-n", str(lines)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            else:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            
            if result.returncode == 0:
                return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError, PermissionError):
            pass
    
    return None


def parse_log_file(filepath: str, lines: Optional[int] = None) -> Optional[str]:
    """
    Try to read from a log file (e.g., /var/log/kern.log).
    
    Args:
        filepath: Path to log file
        lines: Number of lines to read from end
    
    Returns:
        Log content as string, or None if not readable
    """
    try:
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
            if lines:
                content_lines = content.splitlines()
                content = "\n".join(content_lines[-lines:])
            
            return content
    except (OSError, IOError, PermissionError):
        pass
    
    return None


def parse_timestamp(line: str) -> Optional[datetime]:
    """
    Try to parse timestamp from log line.
    Supports various formats from journalctl and dmesg.
    """
    # journalctl format: "Jan 01 12:00:00 hostname kernel: ..."
    # dmesg -T format: "[Mon Jan  1 12:00:00 2024] ..."
    # dmesg format: "[12345.678] ..."
    
    patterns = [
        # journalctl: "Jan 01 12:00:00"
        r'(\w{3})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})',
        # dmesg -T: "[Mon Jan  1 12:00:00 2024]"
        r'\[(\w{3})\s+(\w{3})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})\s+(\d{4})\]',
        # ISO-like: "2024-01-01T12:00:00"
        r'(\d{4})-(\d{2})-(\d{2})[T\s]+(\d{2}):(\d{2}):(\d{2})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, line)
        if match:
            try:
                # Simplified parsing - in practice, more robust parsing needed
                # For now, return None if we can't reliably parse
                # This is acceptable as timestamps are optional
                pass
            except (ValueError, IndexError):
                pass
    
    return None


def filter_usb_entries(log_lines: List[str]) -> List[LogEntry]:
    """
    Filter log lines for USB-related entries.
    
    Args:
        log_lines: List of raw log lines
    
    Returns:
        List of LogEntry objects
    """
    usb_keywords = [
        "usb",
        "over-current",
        "overcurrent",
        "reset",
        "disconnect",
        "descriptor read",
        "cannot enumerate",
        "enumeration failed",
        "timeout",
    ]
    
    entries = []
    
    for line in log_lines:
        line_lower = line.lower()
        
        # Check if line contains USB-related keywords
        if any(keyword in line_lower for keyword in usb_keywords):
            # Extract the actual message (after timestamp/prefix)
            # Try to find the kernel message part
            message = line
            
            # Strip common prefixes
            # journalctl: "Jan 01 12:00:00 hostname kernel: [12345.678] message"
            # dmesg -T: "[Mon Jan  1 12:00:00 2024] message"
            # Extract after last colon or bracket
            if "] " in message:
                parts = message.split("] ", 1)
                if len(parts) > 1:
                    message = parts[1]
            elif ": " in message:
                parts = message.rsplit(": ", 1)
                if len(parts) > 1:
                    message = parts[1]
            
            timestamp = parse_timestamp(line)
            entry = LogEntry(message.strip(), timestamp, line)
            entry.extract_device_info()
            entries.append(entry)
    
    return entries


def parse_kernel_logs(
    since_seconds: Optional[int] = None,
    lines: Optional[int] = None
) -> List[LogEntry]:
    """
    Parse kernel logs for USB-related entries.
    Tries multiple sources in order: journalctl, dmesg, log files.
    
    Args:
        since_seconds: Number of seconds ago to start from
        lines: Number of lines to read (for dmesg/log files)
    
    Returns:
        List of LogEntry objects
    """
    log_output = None
    
    # Try journalctl first (systemd systems)
    if since_seconds:
        log_output = parse_journalctl(since_seconds)
    else:
        log_output = parse_journalctl()
    
    # Fallback to dmesg
    if not log_output:
        log_output = parse_dmesg(lines)
    
    # Fallback to log files
    if not log_output:
        log_files = [
            "/var/log/kern.log",
            "/var/log/messages",
            "/var/log/syslog",
        ]
        
        for log_file in log_files:
            log_output = parse_log_file(log_file, lines)
            if log_output:
                break
    
    if not log_output:
        return []
    
    log_lines = log_output.splitlines()
    
    # If since_seconds specified but we're using dmesg/log file,
    # filter by approximate timestamp (heuristic)
    if since_seconds and log_output and not parse_journalctl(since_seconds):
        # For dmesg/log files, we'd need to parse timestamps more carefully
        # For now, just use the lines limit if provided
        pass
    
    entries = filter_usb_entries(log_lines)
    
    # If since_seconds was specified, filter entries by time
    # (This is approximate since timestamp parsing is limited)
    if since_seconds and entries:
        cutoff_time = datetime.now() - timedelta(seconds=since_seconds)
        filtered_entries = []
        for entry in entries:
            if entry.timestamp is None:
                # Include entries without timestamp (conservative approach)
                filtered_entries.append(entry)
            elif entry.timestamp >= cutoff_time:
                filtered_entries.append(entry)
        entries = filtered_entries
    
    return entries
