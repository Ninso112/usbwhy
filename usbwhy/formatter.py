"""
Output formatting module.

Handles text and JSON output formatting with optional color support.
"""

import json
import sys
from typing import List, Optional

from .analyzer import DeviceAnalysis
from .device_enum import USBDevice
from .log_parser import LogEntry


class Colors:
    """ANSI color codes for terminal output."""
    
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    @staticmethod
    def disable():
        """Disable all colors."""
        Colors.RED = ''
        Colors.YELLOW = ''
        Colors.GREEN = ''
        Colors.BLUE = ''
        Colors.CYAN = ''
        Colors.RESET = ''
        Colors.BOLD = ''


def should_use_colors(no_color: bool, output_stream) -> bool:
    """
    Determine if colors should be used.
    
    Args:
        no_color: Explicit --no-color flag
        output_stream: Output stream (stdout/stderr)
    
    Returns:
        True if colors should be used
    """
    if no_color:
        return False
    
    # Check if output is a TTY
    if hasattr(output_stream, 'isatty'):
        return output_stream.isatty()
    
    return False


def format_device_text(device: USBDevice, indent: int = 0) -> str:
    """Format a single device for text output."""
    prefix = "  " * indent
    lines = []
    
    # Device ID
    device_id_str = f"{prefix}{Colors.BOLD}{device.device_id}{Colors.RESET}"
    if device.busnum and device.devnum:
        device_id_str += f" (Bus {device.busnum}, Device {device.devnum})"
    lines.append(device_id_str)
    
    # Vendor/Product
    vp_id = device.get_id_vendor_product()
    if vp_id:
        vp_line = f"{prefix}  ID: {vp_id}"
        if device.vendor_name or device.product_name:
            name_parts = []
            if device.vendor_name:
                name_parts.append(device.vendor_name)
            if device.product_name:
                name_parts.append(device.product_name)
            vp_line += f" {Colors.CYAN}{' '.join(name_parts)}{Colors.RESET}"
        lines.append(vp_line)
    
    # Class
    if device.device_class:
        lines.append(f"{prefix}  Class: {device.device_class}")
    
    # Speed
    if device.speed:
        lines.append(f"{prefix}  Speed: {device.speed}")
    
    # Driver
    if device.driver:
        lines.append(f"{prefix}  Driver: {Colors.GREEN}{device.driver}{Colors.RESET}")
    else:
        lines.append(f"{prefix}  Driver: {Colors.YELLOW}none{Colors.RESET}")
    
    return "\n".join(lines)


def format_analysis_text(analysis: DeviceAnalysis, verbose: bool = False) -> str:
    """Format device analysis for text output."""
    lines = []
    
    # Device header
    lines.append("")
    lines.append(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}")
    device_header = f"Device: {analysis.device.device_id}"
    vp_id = analysis.device.get_id_vendor_product()
    if vp_id:
        device_header += f" ({vp_id})"
    lines.append(f"{Colors.BOLD}{device_header}{Colors.RESET}")
    lines.append(f"{'=' * 60}")
    
    # Device info
    lines.append(format_device_text(analysis.device, indent=1))
    
    # Issues
    if analysis.issues:
        lines.append("")
        lines.append(f"{Colors.RED}{Colors.BOLD}Issues detected:{Colors.RESET}")
        for issue in analysis.issues:
            lines.append(f"  {Colors.RED}•{Colors.RESET} {issue}")
    else:
        lines.append("")
        lines.append(f"{Colors.GREEN}No obvious issues detected{Colors.RESET}")
    
    # Log summary
    if analysis.log_entries:
        lines.append("")
        summary_parts = []
        if analysis.reset_count > 0:
            summary_parts.append(f"{analysis.reset_count} resets")
        if analysis.disconnect_count > 0:
            summary_parts.append(f"{analysis.disconnect_count} disconnects")
        if analysis.error_count > 0:
            summary_parts.append(f"{Colors.RED}{analysis.error_count} errors{Colors.RESET}")
        if analysis.warning_count > 0:
            summary_parts.append(f"{Colors.YELLOW}{analysis.warning_count} warnings{Colors.RESET}")
        if analysis.over_current_count > 0:
            summary_parts.append(f"{Colors.RED}{analysis.over_current_count} over-current{Colors.RESET}")
        
        if summary_parts:
            lines.append(f"Log summary: {', '.join(summary_parts)}")
        
        # Show log entries in verbose mode
        if verbose:
            lines.append("")
            lines.append(f"{Colors.BOLD}Recent log entries:{Colors.RESET}")
            for entry in analysis.log_entries[-10:]:  # Last 10 entries
                category_color = Colors.RESET
                if entry.category == "error":
                    category_color = Colors.RED
                elif entry.category == "warning":
                    category_color = Colors.YELLOW
                
                lines.append(
                    f"  {category_color}[{entry.category}]{Colors.RESET} {entry.message[:80]}"
                )
    
    return "\n".join(lines)


def format_text(
    analyses: List[DeviceAnalysis],
    unmatched_logs: List[LogEntry],
    verbose: bool = False,
    use_colors: bool = True
) -> str:
    """
    Format analysis results as human-readable text.
    
    Args:
        analyses: List of device analyses
        unmatched_logs: Log entries that couldn't be matched to devices
        verbose: Show detailed log entries
        use_colors: Enable color output
    
    Returns:
        Formatted text string
    """
    if not use_colors:
        Colors.disable()
    
    lines = []
    
    # Header
    lines.append(f"{Colors.BOLD}USB Device Analysis{Colors.RESET}")
    lines.append("")
    
    if not analyses:
        lines.append("No USB devices found or no devices match the specified criteria.")
        return "\n".join(lines)
    
    # Summary
    devices_with_issues = [a for a in analyses if a.issues]
    if devices_with_issues:
        lines.append(
            f"{Colors.YELLOW}{Colors.BOLD}"
            f"Found {len(devices_with_issues)} device(s) with potential issues"
            f"{Colors.RESET}"
        )
    else:
        lines.append(
            f"{Colors.GREEN}{Colors.BOLD}"
            f"All {len(analyses)} device(s) appear to be functioning normally"
            f"{Colors.RESET}"
        )
    lines.append("")
    
    # Device analyses
    for analysis in analyses:
        lines.append(format_analysis_text(analysis, verbose))
    
    # Unmatched logs
    if unmatched_logs:
        lines.append("")
        lines.append(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}")
        lines.append(
            f"{Colors.YELLOW}{Colors.BOLD}"
            f"Unmatched log entries ({len(unmatched_logs)}){Colors.RESET}"
        )
        lines.append(f"{'=' * 60}")
        lines.append(
            "These log entries couldn't be matched to any current device."
        )
        
        if verbose:
            for entry in unmatched_logs[-20:]:  # Last 20 unmatched
                category_color = Colors.RESET
                if entry.category == "error":
                    category_color = Colors.RED
                elif entry.category == "warning":
                    category_color = Colors.YELLOW
                
                lines.append(
                    f"  {category_color}[{entry.category}]{Colors.RESET} {entry.message[:80]}"
                )
    
    return "\n".join(lines)


def format_json(
    analyses: List[DeviceAnalysis],
    unmatched_logs: List[LogEntry]
) -> str:
    """
    Format analysis results as JSON.
    
    Args:
        analyses: List of device analyses
        unmatched_logs: Log entries that couldn't be matched to devices
    
    Returns:
        JSON string
    """
    output = {
        "devices": [],
        "unmatched_logs": [],
        "summary": {
            "total_devices": len(analyses),
            "devices_with_issues": len([a for a in analyses if a.issues]),
        }
    }
    
    # Device analyses
    for analysis in analyses:
        device_data = {
            "device_id": analysis.device.device_id,
            "vendor_id": analysis.device.vendor_id,
            "product_id": analysis.device.product_id,
            "vendor_name": analysis.device.vendor_name,
            "product_name": analysis.device.product_name,
            "device_class": analysis.device.device_class,
            "speed": analysis.device.speed,
            "driver": analysis.device.driver,
            "busnum": analysis.device.busnum,
            "devnum": analysis.device.devnum,
            "issues": analysis.issues,
            "log_summary": {
                "total_entries": len(analysis.log_entries),
                "reset_count": analysis.reset_count,
                "disconnect_count": analysis.disconnect_count,
                "error_count": analysis.error_count,
                "warning_count": analysis.warning_count,
                "over_current_count": analysis.over_current_count,
                "timeout_count": analysis.timeout_count,
                "descriptor_error_count": analysis.descriptor_error_count,
                "enumeration_error_count": analysis.enumeration_error_count,
            },
            "log_entries": [
                {
                    "message": entry.message,
                    "category": entry.category,
                    "device_id": entry.device_id,
                    "vendor_product": entry.vendor_product,
                    "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                }
                for entry in analysis.log_entries
            ],
        }
        output["devices"].append(device_data)
    
    # Unmatched logs
    output["unmatched_logs"] = [
        {
            "message": entry.message,
            "category": entry.category,
            "device_id": entry.device_id,
            "vendor_product": entry.vendor_product,
            "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
        }
        for entry in unmatched_logs
    ]
    
    return json.dumps(output, indent=2, ensure_ascii=False)
