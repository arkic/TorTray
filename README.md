# TorTray

A macOS menu bar application for managing Tor connections with bridge support.

[Uploading gifmethank (2).gif…]

## Description

TorTray is a lightweight macOS system tray application that provides an easy way to start, stop, and configure Tor connections directly from the menu bar. It supports various bridge types including obfs4, Snowflake, and meek-azure for bypassing network restrictions.

## Features

- **Simple Menu Bar Interface**: Start/stop Tor with a single click
- **Bridge Support**: 
  - obfs4 bridges (with custom bridge configuration)
  - Snowflake bridges (built-in configuration)
  - meek-azure bridges (built-in configuration)
  - Direct connections (no bridge)
- **Auto-start**: Option to run on system launch
- **Configuration Management**: Easy config file editing
- **Logging**: View and clear Tor logs
- **Status Monitoring**: Real-time connection status checking

## Requirements

### System Requirements
- macOS (tested on macOS 10.14+)
- Python 3.7 or higher

### Dependencies
- `rumps` - For creating the menu bar application
- `tor` - The Tor binary (install via Homebrew)

### Optional Pluggable Transports
For bridge functionality, you may need:
- `obfs4proxy` - For obfs4 bridges
- `snowflake-client` - For Snowflake bridges  
- `meek-client` - For meek-azure bridges

## Installation

1. **Install Tor and pluggable transports via Homebrew:**
   ```bash
   brew install tor
   brew install obfs4proxy
   brew install snowflake
   ```

2. **Install Python dependencies:**
   ```bash
   pip3 install rumps
   ```

3. **Download and run TorTray:**
   ```bash
   python3 tortray.py
   ```

## Configuration

TorTray creates a configuration file at `~/Library/Application Support/TorTray/config.json` on first run. You can modify this file to:

- Set custom bridge configurations
- Change SOCKS and control ports
- Specify custom paths for Tor and pluggable transports
- Configure obfs4 bridge lines

### Example Configuration

```json
{
  "run_on_launch": false,
  "bridge": "snowflake",
  "tor_path": "tor",
  "socks_port": 9050,
  "control_port": 9051,
  "pt_paths": {
    "obfs4proxy": "/opt/homebrew/bin/obfs4proxy:/usr/local/bin/obfs4proxy",
    "snowflake-client": "/opt/homebrew/bin/snowflake-client:/usr/local/bin/snowflake-client",
    "meek-client": "/opt/homebrew/bin/meek-client:/usr/local/bin/meek-client"
  },
  "obfs4_bridges": [
    "obfs4 IP:PORT FINGERPRINT cert=CERT iat-mode=0"
  ]
}
```

## Usage

1. **Start TorTray**: Run `python3 tortray.py`
2. **Connect to Tor**: Click "Connect" in the menu bar
3. **Change Bridges**: Select from the Bridges submenu
4. **Configure**: Use "Edit Config" to modify settings
5. **View Logs**: Use "Show Tor Logs" to troubleshoot
6. **Auto-start**: Enable "Run on Launch" for automatic startup

## Bridge Types

### Snowflake (Default)
- Works out of the box
- Good for bypassing basic censorship
- No additional configuration required

### obfs4
- Requires custom bridge lines
- Obtain bridges from https://bridges.torproject.org/
- Add bridge lines to the `obfs4_bridges` array in config

### meek-azure
- Uses domain fronting via Azure CDN
- Works in heavily censored networks
- Built-in configuration included

## Files and Directories

- **Config**: `~/Library/Application Support/TorTray/config.json`
- **Logs**: `~/Library/Application Support/TorTray/tor.log`
- **Launch Agent**: `~/Library/LaunchAgents/com.arktor.tray.plist`

## Troubleshooting

### Common Issues

1. **"Missing tor" notification**
   - Install Tor: `brew install tor`

2. **Bridge connection failures**
   - Try different bridge types
   - Check bridge configuration for obfs4
   - View logs for detailed error messages

3. **Pluggable transport errors**
   - Install required transports via Homebrew
   - Check paths in configuration file

### Logs
Use "Show Tor Logs" from the menu to view detailed connection logs and error messages.

## License

This project is open source. Please ensure compliance with local laws regarding Tor usage.

## Security Notice

- This tool is for legitimate privacy and security purposes
- Ensure you comply with local laws and regulations
- Use responsibly and ethically
