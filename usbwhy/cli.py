"""
Command-line interface for usbwhy.
"""

import argparse
import sys
from typing import Optional

from .analyzer import analyze_devices, get_unmatched_logs
from .device_enum import enumerate_devices
from .formatter import format_json, format_text, should_use_colors
from .log_parser import parse_kernel_logs


def parse_device_filter(device_arg: str) -> tuple[Optional[str], Optional[str]]:
    """
    Parse device filter argument.
    Accepts formats:
    - "1-1.2" (bus-device)
    - "1234:5678" (vendor:product)
    
    Returns:
        Tuple of (device_id, vendor_product) - one will be None
    """
    if not device_arg:
        return None, None
    
    # Check for vendor:product format
    if ':' in device_arg and len(device_arg.split(':')) == 2:
        parts = device_arg.split(':')
        if len(parts[0]) == 4 and len(parts[1]) == 4:
            try:
                int(parts[0], 16)
                int(parts[1], 16)
                return None, device_arg.lower()
            except ValueError:
                pass
    
    # Check for bus-device format
    if '-' in device_arg:
        return device_arg, None
    
    return None, None


def filter_devices(devices, device_id_filter: Optional[str], vendor_product_filter: Optional[str]):
    """Filter devices based on device ID or vendor:product ID."""
    if not device_id_filter and not vendor_product_filter:
        return devices
    
    filtered = []
    for device in devices:
        if device_id_filter and device.device_id == device_id_filter:
            filtered.append(device)
        elif vendor_product_filter:
            vp_id = device.get_id_vendor_product()
            if vp_id and vp_id.lower() == vendor_product_filter:
                filtered.append(device)
    
    return filtered


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Diagnose USB device issues by analyzing USB topology and kernel logs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Analyze all USB devices
  %(prog)s --device 1-1.2          # Focus on specific device
  %(prog)s --device 1234:5678      # Focus on vendor:product ID
  %(prog)s --since 3600            # Analyze last hour of logs
  %(prog)s --lines 1000            # Analyze last 1000 log lines
  %(prog)s --json                  # JSON output
  %(prog)s --verbose               # Show detailed log entries
        """
    )
    
    parser.add_argument(
        "--device",
        metavar="ID",
        help="Focus on specific device (bus-device like '1-1.2' or vendor:product like '1234:5678')"
    )
    
    parser.add_argument(
        "--since",
        type=int,
        metavar="SECONDS",
        help="Analyze kernel logs from last N seconds"
    )
    
    parser.add_argument(
        "--lines",
        type=int,
        metavar="N",
        help="Analyze last N lines of kernel logs (for dmesg/log files)"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed log entries"
    )
    
    args = parser.parse_args()
    
    # Parse device filter
    device_id_filter, vendor_product_filter = parse_device_filter(args.device)
    
    # Enumerate USB devices
    try:
        devices = enumerate_devices(use_lsusb=True)
    except Exception as e:
        if args.verbose:
            print(f"Warning: Error enumerating devices: {e}", file=sys.stderr)
        devices = []
    
    if not devices:
        if not args.json:
            print("No USB devices found.", file=sys.stderr)
        else:
            print('{"devices": [], "unmatched_logs": [], "summary": {"total_devices": 0, "devices_with_issues": 0}}')
        sys.exit(0)
    
    # Filter devices if requested
    if device_id_filter or vendor_product_filter:
        devices = filter_devices(devices, device_id_filter, vendor_product_filter)
        
        if not devices:
            if not args.json:
                print(f"No device found matching: {args.device}", file=sys.stderr)
            else:
                print('{"devices": [], "unmatched_logs": [], "summary": {"total_devices": 0, "devices_with_issues": 0}}')
            sys.exit(1)
    
    # Parse kernel logs
    try:
        log_entries = parse_kernel_logs(
            since_seconds=args.since,
            lines=args.lines
        )
    except Exception as e:
        if args.verbose:
            print(f"Warning: Error parsing kernel logs: {e}", file=sys.stderr)
        log_entries = []
    
    # Analyze devices
    try:
        analyses = analyze_devices(devices, log_entries)
        unmatched_logs = get_unmatched_logs(devices, log_entries)
    except Exception as e:
        print(f"Error analyzing devices: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Format and output results
    try:
        if args.json:
            output = format_json(analyses, unmatched_logs)
            print(output)
        else:
            use_colors = should_use_colors(args.no_color, sys.stdout)
            output = format_text(analyses, unmatched_logs, args.verbose, use_colors)
            print(output)
    except Exception as e:
        print(f"Error formatting output: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
