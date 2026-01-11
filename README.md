# usbwhy

usbwhy is a small Linux command-line tool that explains why a USB device is misbehaving. It inspects the USB topology, kernel messages and basic device info, then summarizes common issues such as resets, errors, missing drivers or power problems.

## Installation

usbwhy requires Python 3 and uses only the standard library. No additional dependencies are needed.

Simply clone or download this repository and make the script executable:

```bash
chmod +x usbwhy.py
```

You can run it directly:
```bash
./usbwhy.py
```

Or via Python:
```bash
python3 usbwhy.py
```

To install system-wide, you can copy `usbwhy.py` to a directory in your `PATH` (e.g., `/usr/local/bin/` or `~/.local/bin/`).

### Optional Dependencies

- `lsusb` (from usbutils package): Provides vendor/product names for better device identification
- `journalctl` or `dmesg`: For kernel log access (usually available by default)
- Root access: May be required to read kernel logs depending on system configuration

## Usage Examples

### Basic Overview

Analyze all USB devices and check for issues:

```bash
./usbwhy.py
```

This will:
- List all connected USB devices
- Search recent kernel logs for USB-related messages
- Match log entries to devices
- Display a summary of detected issues

### Focus on a Specific Device

Analyze a specific device by bus-device number:

```bash
./usbwhy.py --device 1-1.2
```

Or by vendor:product ID:

```bash
./usbwhy.py --device 1234:5678
```

### Analyze Recent Logs

Check logs from the last hour:

```bash
./usbwhy.py --since 3600
```

Or analyze the last 1000 lines of logs:

```bash
./usbwhy.py --lines 1000
```

### JSON Output

Get structured JSON output for programmatic processing:

```bash
./usbwhy.py --json
```

### Verbose Mode

Show detailed log entries:

```bash
./usbwhy.py --verbose
```

### Disable Colors

Disable colored output (useful for logging or scripts):

```bash
./usbwhy.py --no-color
```

### Combined Options

```bash
./usbwhy.py --device 1-1.2 --since 3600 --verbose
```

## Interpreting Messages

usbwhy detects and categorizes common USB issues. Here's what different messages mean:

### Frequent Resets/Reconnects

**Message**: "Frequent resets/reconnects (N occurrences) - possible cable, port, or power problem"

**Meaning**: The device is being reset or disconnected repeatedly. This typically indicates:
- Faulty or damaged USB cable
- Loose connection
- Insufficient power (especially with USB hubs)
- Physical port damage

**Action**: Try a different cable, different port, or powered USB hub.

### Over-Current

**Message**: "Over-current detected - device may be drawing too much power or hub has power issue"

**Meaning**: The device is drawing more current than allowed. USB ports have current limits (typically 500mA for USB 2.0, 900mA for USB 3.0).

**Action**: 
- Use a powered USB hub
- Connect device directly to computer port (not through hub)
- Check if device has its own power adapter

### Device Descriptor Errors

**Message**: "Device descriptor read errors - possible hardware connection problem"

**Meaning**: The kernel couldn't read the device's descriptor, which contains basic information about the device.

**Action**: 
- Check cable and connection
- Try different port
- Device may be faulty

### Enumeration Failed

**Message**: "Enumeration failed - device may not be responding properly"

**Meaning**: The device failed to enumerate (identify itself) when connected.

**Action**: Similar to descriptor errors - check cable, port, and device itself.

### USB Timeouts

**Message**: "USB timeouts - device may be slow or unresponsive"

**Meaning**: The device didn't respond to USB commands within the expected time.

**Action**: 
- Device may be overloaded
- Check for other system issues
- Device firmware may have issues

### Missing Driver

**Message**: "No driver bound - device class X may not have a matching kernel module"

**Meaning**: No kernel driver is bound to the device. This could mean:
- Driver is not available for this device
- Driver failed to load
- Device class is not recognized

**Action**: 
- Check if appropriate kernel module needs to be loaded
- Search for device-specific drivers
- Check kernel logs for driver loading errors

### Unknown Device Class

**Message**: "Unknown device class - driver may not be available"

**Meaning**: The device reports an unknown or invalid device class.

**Action**: May indicate a non-standard device or firmware issue.

## Limitations

usbwhy is a heuristic tool designed to help diagnose common USB issues. It has several limitations:

1. **Log Access**: Reading kernel logs may require root privileges or group membership (e.g., `systemd-journal` or `adm` group). If logs are inaccessible, usbwhy will continue but with limited information.

2. **Heuristic Analysis**: The analysis is based on pattern matching and heuristics. It cannot replace detailed kernel debugging tools or hardware diagnostics.

3. **Device Matching**: Matching log entries to devices is done by device IDs or vendor:product IDs. Some log entries may not be matched if they don't contain these identifiers.

4. **Timestamp Parsing**: Timestamp parsing from kernel logs may be limited, especially for older log formats.

5. **System-Dependent**: Behavior depends on your Linux distribution and kernel version. Different systems may have different log formats or sysfs structures.

6. **No Real-Time Monitoring**: usbwhy analyzes current state and historical logs. It does not monitor devices in real-time.

## How It Works

1. **Device Enumeration**: Reads USB device information from `/sys/bus/usb/devices/` and optionally enriches it with `lsusb` output.

2. **Log Parsing**: Attempts to read kernel logs from:
   - `journalctl` (systemd systems)
   - `dmesg` (fallback)
   - Log files like `/var/log/kern.log` (if readable)

3. **Matching**: Matches log entries to devices by device ID (e.g., "1-1.2") or vendor:product ID (e.g., "1234:5678").

4. **Analysis**: Applies heuristics to detect common issues:
   - Counts resets, disconnects, errors
   - Detects missing drivers
   - Identifies power issues
   - Flags descriptor/enumeration problems

5. **Reporting**: Formats results as human-readable text or JSON.

## License

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

See the [LICENSE](LICENSE) file for the full GPLv3 license text.
