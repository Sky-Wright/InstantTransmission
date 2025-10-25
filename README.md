# InstantTransmission

**Zero-configuration peer-to-peer file sharing for Windows 10/11**

Share files across your local network with automatic peer discovery - no setup required.

## Beta Release

**Status:** Beta 1 - Tested on Windows 11, needs broader testing

This worked reliably on the developer's Windows 11 machines but **needs community testing** on different Windows configurations. If you encounter issues, please report them!

## What Works

### Core Features
- **Automatic Peer Discovery** - Find other users on your network instantly via mDNS
- **File Sharing** - Share your Public folder via WebDAV (read-only for security)
- **Folder Downloads** - Download entire folders while preserving directory structure
- **Fast Transfers** - High-performance Waitress server (10+ MB/s on gigabit LAN)
- **Progress Tracking** - Real-time download speed and ETA
- **Dark Mode UI** - Custom file browser with modern dark theme
- **System Tray** - Runs in background, access via tray icon
- **Auto Firewall Setup** - Configures Windows Firewall automatically (requires admin on first run)

### What's Tested
- ✅ Windows 11 (developer machines)
- ✅ Local network file sharing (same subnet)
- ✅ Multiple peers discovering each other
- ✅ Large file transfers (multi-GB tested)
- ✅ Folder structure preservation

### Design Decisions
- **Windows only** - No Linux/Mac support yet
- **Read-only sharing** - Security by design (peers can't modify your files)
- **No authentication** - Simplicity over complexity (use on trusted networks)
- **Local network only** - Intentional security feature (never exposed to internet)

## Quick Start

### Download & Run

1. Download `InstantTransmission-Portable.zip` from [Releases](https://github.com/Sky-Wright/InstantTransmission/releases)
2. Extract anywhere
3. Run `instant_transmission.exe`
4. Grant admin permission when prompted (needed for firewall setup)
5. Look for the tray icon in your system tray

### Using InstantTransmission

**Sharing files:**
- Put files you want to share in `C:\Users\YourName\Public`
- They're automatically shared to discovered peers

**Browsing peers:**
- Right-click the tray icon
- Select a peer from the "Discovered Peers" menu
- Browse and download files via the dark mode file browser

**That's it!** No configuration needed.

## For Developers

**Note:** Source code includes unfinished features (password auth, remote desktop). These are not in the Beta 1 build and may cause issues if you try to rebuild.

```bash
# Setup
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Run
python instant_transmission.py
```

## System Requirements

- **Windows 10/11 (64-bit)**
- **Administrator privileges** (one-time, for firewall setup)
- **Local network connection**

## Architecture

Built with Python using:
- **Waitress** - High-performance WSGI server
- **WsgiDAV** - WebDAV protocol implementation
- **Zeroconf** - mDNS service discovery
- **Tkinter** - Cross-platform GUI framework
- **pystray** - System tray integration

## Security

- **Local network only** - Not exposed to the internet
- **Read-only sharing** - Peers can only download, not upload/modify
- **Firewall protected** - Automatic Windows Firewall rule setup
- **No cloud services** - Everything stays on your network

## Contributing

This is a beta release! If you:
- Find bugs → Open an issue
- Have Windows 10 → Test it and report back
- Want features → Suggest them in discussions

## License

GPL-3.0 - Open source begits open source

## Acknowledgments

Built for local network file sharing without the hassle of mapped drives, shared folders, or cloud services.
