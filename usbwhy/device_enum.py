"""
USB device enumeration module.

Reads USB device information from sysfs and optionally uses lsusb
as a fallback or supplementary source.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


class USBDevice:
    """Represents a USB device with its properties."""

    def __init__(self, device_id: str):
        self.device_id = device_id  # e.g., "1-1.2"
        self.vendor_id: Optional[str] = None
        self.product_id: Optional[str] = None
        self.vendor_name: Optional[str] = None
        self.product_name: Optional[str] = None
        self.device_class: Optional[str] = None
        self.speed: Optional[str] = None
        self.driver: Optional[str] = None
        self.busnum: Optional[str] = None
        self.devnum: Optional[str] = None
        self.parent_id: Optional[str] = None

    def get_id_vendor_product(self) -> Optional[str]:
        """Return vendor:product ID string, or None if not available."""
        if self.vendor_id and self.product_id:
            return f"{self.vendor_id}:{self.product_id}"
        return None

    def __repr__(self) -> str:
        return f"USBDevice({self.device_id}, {self.get_id_vendor_product()})"


def read_sysfs_file(sysfs_path: Path, filename: str) -> Optional[str]:
    """Read a file from sysfs, returning None if not found or unreadable."""
    file_path = sysfs_path / filename
    try:
        if file_path.exists():
            return file_path.read_text().strip()
    except (OSError, IOError, PermissionError):
        pass
    return None


def parse_device_id(device_dir: str) -> Optional[str]:
    """
    Parse device ID from sysfs directory name.
    Valid formats: "1-0", "1-1", "1-1.2", "2-4.1.3"
    """
    # USB device directories match pattern: digit-digits with optional .digit suffix
    pattern = r'^(\d+)-(\d+(?:\.\d+)*)$'
    match = re.match(pattern, device_dir)
    if match:
        return device_dir
    return None


def get_device_hierarchy(sysfs_path: Path) -> Dict[str, Optional[str]]:
    """
    Determine parent relationships by parsing device tree.
    Returns dict mapping device_id -> parent_id.
    """
    hierarchy = {}
    devices_path = sysfs_path / "devices"
    
    if not devices_path.exists():
        return hierarchy
    
    # Read all device directories
    for device_dir in devices_path.iterdir():
        if not device_dir.is_dir():
            continue
        
        device_id = parse_device_id(device_dir.name)
        if not device_id:
            continue
        
        # Try to find parent by reading uevent or checking device structure
        # Parent is typically one level up in the hierarchy
        uevent_path = device_dir / "uevent"
        parent_id = None
        
        if uevent_path.exists():
            try:
                uevent_content = uevent_path.read_text()
                # Look for USB_DEVICE entry which might contain parent info
                # This is a heuristic - actual parent detection from sysfs can be complex
                pass
            except (OSError, IOError):
                pass
        
        # Simple heuristic: parent is the device without the last segment
        # e.g., parent of "1-1.2" is "1-1", parent of "1-1" is "1-0"
        parts = device_id.split('.')
        if len(parts) > 1:
            parent_id = '.'.join(parts[:-1])
        elif device_id.endswith('-0'):
            # Root hub, no parent
            parent_id = None
        else:
            # Device directly on bus, parent is bus root
            bus_part = device_id.split('-')[0]
            parent_id = f"{bus_part}-0"
        
        hierarchy[device_id] = parent_id
    
    return hierarchy


def enumerate_from_sysfs(sysfs_path: Path = Path("/sys/bus/usb/devices")) -> List[USBDevice]:
    """
    Enumerate USB devices from sysfs.
    
    Args:
        sysfs_path: Path to /sys/bus/usb/devices (default)
    
    Returns:
        List of USBDevice objects
    """
    devices = []
    
    if not sysfs_path.exists():
        return devices
    
    hierarchy = get_device_hierarchy(sysfs_path)
    
    for device_dir in sysfs_path.iterdir():
        if not device_dir.is_dir():
            continue
        
        device_id = parse_device_id(device_dir.name)
        if not device_id:
            continue
        
        device = USBDevice(device_id)
        device.parent_id = hierarchy.get(device_id)
        
        # Read device properties from sysfs
        device.vendor_id = read_sysfs_file(device_dir, "idVendor")
        device.product_id = read_sysfs_file(device_dir, "idProduct")
        device.device_class = read_sysfs_file(device_dir, "bDeviceClass")
        device.speed = read_sysfs_file(device_dir, "speed")
        
        # Driver is in driver symlink target
        driver_link = device_dir / "driver"
        if driver_link.exists() and driver_link.is_symlink():
            try:
                driver_target = driver_link.readlink()
                device.driver = driver_target.name
            except (OSError, IOError):
                pass
        
        # Bus and device numbers
        device.busnum = read_sysfs_file(device_dir, "busnum")
        device.devnum = read_sysfs_file(device_dir, "devnum")
        
        # Only add devices that have at least vendor/product IDs (real devices, not hubs)
        if device.vendor_id or device.product_id:
            devices.append(device)
    
    return devices


def get_lsusb_info() -> Optional[str]:
    """
    Try to get lsusb output if available.
    Returns None if lsusb is not found or fails.
    """
    try:
        result = subprocess.run(
            ["lsusb"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def parse_lsusb_v(lsusb_v_output: str) -> Dict[str, Dict[str, str]]:
    """
    Parse detailed lsusb -v output to extract vendor/product names.
    Returns dict mapping vendor:product -> {vendor_name, product_name}
    """
    info = {}
    current_vendor_product = None
    current_info = {}
    
    for line in lsusb_v_output.splitlines():
        line = line.strip()
        
        # Bus and device line: "Bus 001 Device 002: ID 1234:5678 Vendor Product"
        if line.startswith("Bus ") and "Device " in line and "ID " in line:
            # Extract vendor:product
            id_match = re.search(r'ID (\w{4}):(\w{4})', line)
            if id_match:
                vendor_id = id_match.group(1)
                product_id = id_match.group(2)
                current_vendor_product = f"{vendor_id}:{product_id}"
                current_info = {}
                
                # Try to extract names from this line
                parts = line.split("ID ")[1].split(" ", 2)
                if len(parts) >= 3:
                    current_info["vendor_name"] = parts[2] if len(parts[2]) > 0 else None
                    current_info["product_name"] = None  # Usually combined in lsusb short output
                else:
                    # Look for idVendor/idProduct in next lines
                    pass
        
        # idVendor line
        if "idVendor" in line and current_vendor_product:
            match = re.search(r'idVendor\s+0x\w+\s+(\S.+)', line)
            if match:
                current_info["vendor_name"] = match.group(1).strip()
        
        # idProduct line
        if "idProduct" in line and current_vendor_product:
            match = re.search(r'idProduct\s+0x\w+\s+(\S.+)', line)
            if match:
                current_info["product_name"] = match.group(1).strip()
            
            # Save when we get product (usually comes after vendor)
            if current_vendor_product:
                info[current_vendor_product] = current_info.copy()
                current_vendor_product = None
    
    return info


def enrich_devices_with_lsusb(devices: List[USBDevice]) -> None:
    """
    Enrich device list with vendor/product names from lsusb if available.
    """
    lsusb_output = get_lsusb_info()
    if not lsusb_output:
        return
    
    try:
        # Try to get detailed output
        result = subprocess.run(
            ["lsusb", "-v"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            lsusb_info = parse_lsusb_v(result.stdout)
            
            # Match devices with lsusb info
            for device in devices:
                vp_id = device.get_id_vendor_product()
                if vp_id and vp_id in lsusb_info:
                    info = lsusb_info[vp_id]
                    if "vendor_name" in info:
                        device.vendor_name = info["vendor_name"]
                    if "product_name" in info:
                        device.product_name = info["product_name"]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # Fall back to simple lsusb parsing
        lsusb_info = parse_lsusb_v(lsusb_output)
        for device in devices:
            vp_id = device.get_id_vendor_product()
            if vp_id and vp_id in lsusb_info:
                info = lsusb_info[vp_id]
                if "vendor_name" in info:
                    device.vendor_name = info["vendor_name"]
                if "product_name" in info:
                    device.product_name = info["product_name"]


def enumerate_devices(use_lsusb: bool = True) -> List[USBDevice]:
    """
    Enumerate all USB devices.
    
    Args:
        use_lsusb: Whether to try enriching with lsusb information
    
    Returns:
        List of USBDevice objects
    """
    devices = enumerate_from_sysfs()
    
    if use_lsusb:
        try:
            enrich_devices_with_lsusb(devices)
        except Exception:
            # Silently fail if lsusb enrichment fails
            pass
    
    return devices
