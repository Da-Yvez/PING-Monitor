# PING Monitor

A powerful, real-time network monitoring application built with Python and tkinter that continuously monitors the availability and latency of multiple hosts simultaneously.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)

## Features

- 🎯 **Real-time Network Monitoring** - Continuously ping multiple hosts and track their status
- 📊 **Live Statistics Dashboard** - View sent/received packets, packet loss, latency (min/avg/max), and uptime percentage
- 📈 **Graphical Visualization** - Built-in sparkline graphs showing latency trends over time
- 🎨 **Modern Dark Theme UI** - Sleek, professional interface with dark mode aesthetics
- ⚡ **Multi-threaded Architecture** - Efficient concurrent monitoring of multiple hosts without blocking
- 💾 **Persistent Configuration** - Automatically saves and restores hosts and window settings
- 📤 **CSV Export** - Export monitoring data for analysis in spreadsheet applications
- 🔔 **Visual Alerts** - Blinking indicators when hosts go down
- ⏱️ **Configurable Ping Interval** - Adjust monitoring frequency per your needs
- 🌐 **Flexible Host Support** - Monitor IPs, domain names, or URLs (auto-normalizes to hostnames)

## Screenshots

The application features a comprehensive dashboard showing:
- Host status (Up/Down)
- Packet statistics (Sent, Received, Loss %)
- Latency metrics (Last, Min, Avg, Max in milliseconds)
- Uptime percentage
- Last response message
- Live latency graphs with customizable legend

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/Da-Yvez/PING-Monitor.git
   cd PING-Monitor
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   
   *Note: This application primarily uses Python standard library modules (tkinter, threading, subprocess). No external dependencies are required for basic functionality.*

3. **Run the application**
   ```bash
   python app.py
   ```

## Usage

### Adding Hosts

1. Click the **"Add Host"** button or use the menu: `Hosts > Add Host`
2. Enter the hostname, IP address, or URL you want to monitor
3. The application will automatically normalize URLs to hostnames
4. Monitoring begins immediately

### Removing Hosts

1. Select one or more hosts in the list
2. Click the **"Remove"** button or press `Delete` key
3. Or use the menu: `Hosts > Remove Selected`

### Viewing Statistics

The main window displays real-time statistics for each monitored host:
- **Status**: Current state (Up/Down/Unknown)
- **Sent**: Total ping packets sent
- **Rcvd**: Total ping packets received
- **Loss%**: Packet loss percentage
- **Last (ms)**: Most recent latency
- **Min/Avg/Max (ms)**: Latency statistics
- **Uptime%**: Percentage of successful pings
- **Message**: Last response or error message

### Graphical View

- Toggle the graph view: `View > Toggle Graph`
- Select which hosts to display: `View > Select Graph Hosts`
- Click legend items to show/hide individual host graphs
- Graphs display the last 120 data points

### Exporting Data

Export current statistics to CSV:
1. Menu: `File > Export CSV`
2. Choose a save location
3. Data includes all current statistics for all monitored hosts

### Customizing Ping Interval

Adjust how frequently hosts are pinged:
1. Menu: `Settings > Set Ping Interval`
2. Enter interval in seconds (minimum 0.2s, default 1.0s)
3. New interval applies to all hosts

## Configuration Files

### `hosts.json`
Stores the list of monitored hosts. Example:
```json
[
  "127.0.0.1",
  "192.168.1.1",
  "google.com",
  "github.com"
]
```

### `.ping_monitor_settings.json`
Located in your home directory, stores:
- Window size and position
- Column visibility preferences
- UI state preferences

## Building Executable

To create a standalone executable using PyInstaller:

```bash
pyinstaller new_ping_app.spec
```

The executable will be created in the `dist/` directory.

## Architecture

### Core Components

- **`app.py`** - Main application with tkinter GUI
  - `PingApp` class: Main window and UI management
  - Real-time statistics display using ttk.Treeview
  - Canvas-based graphing for latency visualization
  - Multi-threaded update handling

- **`ping_manager.py`** - Backend monitoring engine
  - `PingManager`: Coordinates multiple ping workers
  - `PingWorker`: Individual threaded ping executor per host
  - `HostStats`: Data class for statistics tracking
  - Cross-platform ping implementation (Windows/Linux/macOS)

### Threading Model

- Main thread: UI updates and event handling
- Worker threads: One per monitored host, continuously pinging
- Queue-based communication: Workers push updates, UI drains queue
- Thread-safe operations using locks and events

## Platform Compatibility

The application is fully cross-platform and automatically detects the operating system to use appropriate ping commands:

- **Windows**: Uses `ping -n 1 -w 1000`
- **Linux/macOS**: Uses `ping -n -c 1 -W 1`
- Supports both IPv4 and IPv6

## Keyboard Shortcuts

- **Delete**: Remove selected host(s)
- **Double-click**: Toggle host selection
- **Click blank area**: Deselect all

## License

This project is open source and available under the [MIT License](LICENSE).

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## Author

**Da-Yvez** - [GitHub](https://github.com/Da-Yvez)

## Acknowledgments

- Built with Python's tkinter for cross-platform GUI
- Uses system ping utilities for reliable network testing
- Inspired by network monitoring tools like MTR and PingPlotter

---

**Happy Monitoring! 🚀**
