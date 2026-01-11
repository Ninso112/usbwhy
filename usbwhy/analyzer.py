"""
Heuristic analysis module.

Analyzes USB devices and log entries to detect common issues.
"""

from collections import defaultdict
from typing import Dict, List

from .device_enum import USBDevice
from .log_parser import LogEntry


class DeviceAnalysis:
    """Analysis results for a single device."""

    def __init__(self, device: USBDevice):
        self.device = device
        self.log_entries: List[LogEntry] = []
        self.issues: List[str] = []
        self.reset_count = 0
        self.disconnect_count = 0
        self.error_count = 0
        self.warning_count = 0
        self.over_current_count = 0
        self.timeout_count = 0
        self.descriptor_error_count = 0
        self.enumeration_error_count = 0

    def add_log_entry(self, entry: LogEntry):
        """Add a log entry to this device's analysis."""
        self.log_entries.append(entry)
        
        # Count by category
        if entry.category == "reset":
            self.reset_count += 1
        elif entry.category == "disconnect":
            self.disconnect_count += 1
        elif entry.category == "error":
            self.error_count += 1
        elif entry.category == "warning":
            self.warning_count += 1
        elif entry.category == "over_current":
            self.over_current_count += 1
        elif entry.category == "timeout":
            self.timeout_count += 1
        elif entry.category == "descriptor_error":
            self.descriptor_error_count += 1
        elif entry.category == "enumeration_error":
            self.enumeration_error_count += 1

    def analyze(self):
        """Run heuristic analysis and populate issues list."""
        # Check for frequent resets/reconnects
        total_resets = self.reset_count + self.disconnect_count
        if total_resets >= 5:
            self.issues.append(
                f"Frequent resets/reconnects ({total_resets} occurrences) - "
                "possible cable, port, or power problem"
            )
        elif total_resets >= 3:
            self.issues.append(
                f"Multiple resets/reconnects ({total_resets} occurrences) - "
                "check cable and port connection"
            )
        
        # Check for over-current issues
        if self.over_current_count > 0:
            self.issues.append(
                f"Over-current detected ({self.over_current_count} times) - "
                "device may be drawing too much power or hub has power issue"
            )
        
        # Check for descriptor errors
        if self.descriptor_error_count > 0:
            self.issues.append(
                f"Device descriptor read errors ({self.descriptor_error_count} times) - "
                "possible hardware connection problem"
            )
        
        # Check for enumeration errors
        if self.enumeration_error_count > 0:
            self.issues.append(
                f"Enumeration failed ({self.enumeration_error_count} times) - "
                "device may not be responding properly"
            )
        
        # Check for timeout errors
        if self.timeout_count > 0:
            self.issues.append(
                f"USB timeouts ({self.timeout_count} times) - "
                "device may be slow or unresponsive"
            )
        
        # Check for missing driver
        if self.device.driver is None and self.device.device_class:
            # Unknown device class or no driver bound
            if self.device.device_class in ["00", "0", "ff"]:
                self.issues.append(
                    "Unknown device class - driver may not be available"
                )
            else:
                self.issues.append(
                    f"No driver bound - device class {self.device.device_class} "
                    "may not have a matching kernel module"
                )
        
        # Check for general errors
        if self.error_count >= 3:
            self.issues.append(
                f"Multiple errors detected ({self.error_count} times) - "
                "device may be malfunctioning"
            )


def match_logs_to_devices(
    devices: List[USBDevice],
    log_entries: List[LogEntry]
) -> Dict[USBDevice, List[LogEntry]]:
    """
    Match log entries to devices based on device IDs or vendor:product IDs.
    
    Args:
        devices: List of USB devices
        log_entries: List of log entries
    
    Returns:
        Dict mapping device to list of matched log entries
    """
    device_logs: Dict[USBDevice, List[LogEntry]] = defaultdict(list)
    
    # Build lookup maps
    devices_by_id: Dict[str, USBDevice] = {}
    devices_by_vp: Dict[str, List[USBDevice]] = defaultdict(list)
    
    for device in devices:
        if device.device_id:
            devices_by_id[device.device_id] = device
        
        vp_id = device.get_id_vendor_product()
        if vp_id:
            devices_by_vp[vp_id].append(device)
    
    # Match log entries to devices
    for entry in log_entries:
        matched = False
        
        # Try device ID match first
        if entry.device_id and entry.device_id in devices_by_id:
            device = devices_by_id[entry.device_id]
            device_logs[device].append(entry)
            matched = True
        
        # Try vendor:product match
        if not matched and entry.vendor_product and entry.vendor_product in devices_by_vp:
            for device in devices_by_vp[entry.vendor_product]:
                device_logs[device].append(entry)
            matched = True
    
    return device_logs


def analyze_devices(
    devices: List[USBDevice],
    log_entries: List[LogEntry]
) -> List[DeviceAnalysis]:
    """
    Analyze USB devices and their associated log entries.
    
    Args:
        devices: List of USB devices
        log_entries: List of log entries
    
    Returns:
        List of DeviceAnalysis objects
    """
    # Match logs to devices
    device_logs = match_logs_to_devices(devices, log_entries)
    
    # Create analysis for each device
    analyses = []
    
    for device in devices:
        analysis = DeviceAnalysis(device)
        
        # Add matched log entries
        for entry in device_logs.get(device, []):
            analysis.add_log_entry(entry)
        
        # Run analysis
        analysis.analyze()
        
        analyses.append(analysis)
    
    # Also create analyses for devices with logs but not in device list
    # (disconnected devices that left traces in logs)
    for device, entries in device_logs.items():
        if device not in devices:
            analysis = DeviceAnalysis(device)
            for entry in entries:
                analysis.add_log_entry(entry)
            analysis.analyze()
            analyses.append(analysis)
    
    return analyses


def get_unmatched_logs(
    devices: List[USBDevice],
    log_entries: List[LogEntry]
) -> List[LogEntry]:
    """
    Get log entries that couldn't be matched to any device.
    
    Args:
        devices: List of USB devices
        log_entries: List of log entries
    
    Returns:
        List of unmatched log entries
    """
    device_logs = match_logs_to_devices(devices, log_entries)
    matched_entries = set()
    
    for entries in device_logs.values():
        matched_entries.update(entries)
    
    return [entry for entry in log_entries if entry not in matched_entries]
