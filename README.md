# System Monitor Widget 🖥️⚡

[![Download Standalone Executable](https://img.shields.io/badge/Download-sys__monitor.exe-brightgreen?style=for-the-badge&logo=windows)](https://github.com/Ratul-NotFound/System-Monitor-Windows-/raw/main/bin/sys_monitor.exe)

A lightweight, always-on-top, floating PC performance monitor widget for Windows. Designed with inspiration from the Ubuntu status bar and GNOME extensions, this widget sits unobtrusively on your screen, providing high-contrast, real-time system metrics with ultra-low resource usage.

---

## Features ✨
- 🖥️ **CPU Usage & Temperatures**: Monitors load and aggregates individual core temperatures, displaying the maximum temp (compatible with AMD Ryzen & Intel).
- 🎮 **Universal GPU Metrics**: Auto-discovers and reads load and temperature for any GPU vendor (Nvidia, AMD Radeon, Intel HD/UHD/Iris Xe).
- 💾 **RAM Monitor**: Shows real-time memory utilization with high-load color changes.
- 🌐 **Network Speed**: Displays current download/upload speeds dynamically.
- 📈 **Sparkline Graphs**: Compact, color-coded level indicators for CPU, RAM, and GPU.
- 🎯 **Snapping & Pinning**: Snaps cleanly to screen boundaries and stays "Always on Top" (optional).
- 🌗 **Premium Themes**: Choose between Ubuntu Dark, Ubuntu Classic (Aubergine), Obsidian, Cyberpunk, and Matrix.
- 🚀 **Zero-UAC Startup**: Automatically runs at Windows logon with Highest Privileges via Task Scheduler (no UAC popups on startup).

---

## Clean Code Directory Structure 📁
When pushing this codebase to GitHub, the folder is structured cleanly:
- `app.py`: The main Python Tkinter widget application.
- `LibreHardwareMonitorLib.dll`: The v0.9.6 kernel-interfacing C# assembly library.
- `System.Memory.dll` & dependencies: Required .NET assemblies for C# bindings.
- `run.bat` & `launch.vbs`: Helper wrappers to run the widget silently in the background.
- `requirements.txt`: Minimal required dependencies (`pythonnet`, `psutil`).
- `.gitignore`: Excludes virtual environments (`.venv`), local configs, and build files.

---

## Installation & Running 🚀

### Prerequisites
- Windows 10 or Windows 11.
- Python 3.8 or newer.

### Quick Run (From Source)
1. Double-click `run.bat`.
2. The launcher will automatically configure a virtual environment, install the small requirements (`psutil`, `pythonnet`), and launch the widget.
3. Accept the Windows UAC elevation prompt (needed to load the low-level hardware kernel driver).

---

## Building a Standalone EXE 📦
You can package the entire application into a single, standalone executable:
1. Open your terminal in this directory and run:
   ```bash
   pip install pyinstaller
   ```
2. Build the EXE:
   ```bash
   pyinstaller --noconsole --onefile --name "system_monitor" --add-data "*.dll;." app.py
   ```
3. Your compiled `system_monitor.exe` will be located inside the `dist/` directory! You can drag it to your Desktop and run it directly.

---

## Customization & Options ⚙️
Right-click on the widget anywhere to show the options menu:
- **Always on Top**: Toggle pinning behavior.
- **Start with Windows**: Automatically configure a Task Scheduler logon task (bypasses Windows Startup folder UAC blocks).
- **Modules**: Enable/Disable individual readouts (CPU, RAM, GPU, Network).
- **Opacity**: Adjust transparency (30% to 100%).
- **Themes**: Switch color palettes.

---

## License 📄
This project is open-source. LibreHardwareMonitorLib is distributed under the Mozilla Public License 2.0.
