# InstantTransmission

Zero-configuration local file sharing utility for Windows.

## ⚠️ Project Status

**Last Working Build:** June 7, 2025 (file date: `instant_transmission.exe`)

This repository is primarily for **source code backup**. The source contains both **tested working features** and **untested WIP code** that was added after the last successful build. Features may not work as expected if rebuilt from current source.

### ✅ Working Features (Confirmed in June 7 Build)

- **WebDAV File Sharing** - Share files via local WebDAV server (port 8080)
- **mDNS Peer Discovery** - Automatic discovery of other InstantTransmission instances on LAN
- **Dark Mode File Explorer** - Custom Tkinter GUI for browsing/downloading files from peers
- **System Tray Integration** - Background operation with tray icon and context menu
- **Folder Downloads** - Download entire folders with directory structure preservation
- **Download Progress** - Real-time speed (MB/s) and ETA display
- **Automatic Firewall Configuration** - Sets up Windows Firewall rules (requires admin)
- **High-Performance Server** - Waitress WSGI server for fast transfers

### ⚠️ WIP/Untested Features (Source Code Only)

These features exist in the source code but were **added after the last build** and have **NOT been tested**:

- **Password Authentication** (`password_manager.py`, `auth_controller.py`) - Added but never integrated
- **Remote Desktop Control** (`remote_desktop.py`) - Screen streaming + remote input, created July 2, 2025
- **Control Request Server** - HTTP endpoint for remote desktop requests

**Building from current source will likely fail** due to incomplete integration of these WIP features.

## Installation & Usage

### For End Users (Recommended)

Use the pre-built executable from June 7, 2025:

1. Navigate to `dist/instant_transmission/`
2. Run `instant_transmission.exe` (requires admin privileges for firewall setup)
3. Application will:
   - Create system tray icon
   - Serve your Public folder via WebDAV
   - Discover other peers on the network
4. Right-click tray icon → Select a peer → Browse and download files

### For Developers

**Note:** Current source code has untested WIP features that may cause errors.

```bash
# Setup
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Run (WIP features may not work)
python instant_transmission.py
```

## Requirements

- **Windows 10/11 (64-bit)**
- **Administrator privileges** (for firewall configuration)
- **Python 3.7+** (for development)

### Dependencies

```
wsgidav>=4.0.0
waitress>=2.1.2
zeroconf>=0.47.0
pystray>=0.19.0
requests>=2.25.0
netifaces>=0.11.0
Pillow>=9.0.0

# WIP features (not in working build):
mss>=6.0.0
pynput>=1.7.0
```

## Architecture

### Working Components (June 7 Build)

- `instant_transmission.py` - Main entry point
- `src/webdav_server.py` - Waitress-based WebDAV server
- `src/mdns_discovery.py` - mDNS service registration/browsing
- `src/system_tray.py` - System tray icon and menu
- `src/file_explorer.py` - Dark mode file browser GUI
- `src/admin_utils.py` - Admin privilege handling and firewall setup

### WIP Components (Not in Build)

- `src/remote_desktop.py` - Screen streaming server/client (untested)
- `src/password_manager.py` - Password storage (untested)
- `src/auth_controller.py` - Authentication controller (untested)

## Building

**Warning:** Current source may not build correctly due to WIP features not being fully integrated.

```bash
pyinstaller instant_transmission.spec
```

Note: You may need to remove/comment out WIP imports for a successful build.

## Known Issues

- Current source imports WIP modules that may cause runtime errors
- Remote desktop feature was never completed or tested
- Password authentication was scaffolded but not integrated with WebDAV server

## Performance

Real-world testing (June 7 build):
- **Transfer speeds:** >10 MB/s on gigabit LAN
- **Peer discovery:** <2 seconds on same subnet
- **Folder downloads:** Preserves full directory structure

## Security Notes

- File sharing is **local network only**
- WebDAV server is **read-only** by default
- Requires **explicit firewall rule** (auto-configured on first run)
- WIP password features are **not active** in working build

## License

To be determined.

## Backup Repository

This repository exists primarily for **source code backup**. The last confirmed working build is from June 7, 2025. Use WIP features at your own risk.
