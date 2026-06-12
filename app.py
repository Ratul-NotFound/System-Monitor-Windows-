import os
import sys
import json
import time
import threading
import tkinter as tk
from tkinter import Menu, messagebox
from tkinter import font as tkfont
import psutil
import subprocess
import ctypes

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

CONFIG_FILE = "config.json"

THEMES = {
    "Ubuntu Classic": {
        "bg": "#300A24",        # Ubuntu Aubergine
        "accent": "#FF6F3B",    # Bright Orange for labels
        "text": "#FFFFFF",      # Pure White for readability
        "muted": "#5A2D4E",      # Darker Aubergine for progress track
        "muted_text": "#B39EAE"  # Light Aubergine for separators
    },
    "Ubuntu Dark": {
        "bg": "#161616",        # Very Dark Charcoal
        "accent": "#FF6F3B",    # Bright Orange
        "text": "#FFFFFF",      # Pure White
        "muted": "#3E3E42",      # Medium Gray
        "muted_text": "#71717A"  # Gray
    },
    "Obsidian": {
        "bg": "#0B0B0C",        # Ultra Dark Slate
        "accent": "#38BDF8",    # Sky Blue
        "text": "#FFFFFF",      # Pure White
        "muted": "#27272A",      # Border/Bar grey
        "muted_text": "#71717A"  # Gray
    },
    "Cyberpunk": {
        "bg": "#0F051D",        # Deep Cyber Dark
        "accent": "#FF2A85",    # Hot Pink
        "text": "#FFFFFF",      # Pure White
        "muted": "#2E0F54",      # Dark Purple
        "muted_text": "#6B21A8"  # Purple
    },
    "Matrix Green": {
        "bg": "#000000",        # Pure Black
        "accent": "#39FF14",    # Neon Green
        "text": "#FFFFFF",      # Pure White for readability
        "muted": "#1A331A",      # Dark Green
        "muted_text": "#008F11"  # Muted Green
    }
}

class SystemMonitorWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("System Monitor")
        
        # Hide borders and title bar
        self.root.overrideredirect(True)
        
        # Load user configuration
        self.config = self.load_config()
        
        # GUI Preferences
        self.always_on_top = self.config.get("always_on_top", True)
        self.opacity = self.config.get("opacity", 0.85)
        self.theme_name = self.config.get("theme", "Ubuntu Dark")
        self.compact_mode = self.config.get("compact_mode", False)
        
        # Module visibilities
        self.show_cpu = self.config.get("show_cpu", True)
        self.show_ram = self.config.get("show_ram", True)
        self.show_gpu = self.config.get("show_gpu", True)
        self.show_net = self.config.get("show_net", True)
        
        # Hardware data caches
        self.cpu_usage = 0.0
        self.cpu_temp = None
        self.ram_usage = 0.0
        
        self.gpu_detected = False
        self.gpu_usage = 0.0
        self.gpu_temp = None
        
        self.net_speed_text = "↓ 0 B/s"
        self.prev_net_sent = psutil.net_io_counters().bytes_sent
        self.prev_net_recv = psutil.net_io_counters().bytes_recv
        
        self.check_gpu_presence()
        
        # Initialize native LibreHardwareMonitor DLL
        self.init_libre_hardware_monitor()
        
        # Dimensions & Fonts
        self.height = 24  # Space-efficient height
        self.corner_radius = 6
        self.label_font = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        
        # Calculate dynamic size
        self.width = self.calculate_width()
        
        # Screen position
        screen_w = self.root.winfo_screenwidth()
        x = self.config.get("x", screen_w - self.width - 20)
        y = self.config.get("y", 20)
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
        
        # Configure window attributes
        self.root.attributes("-alpha", self.opacity)
        self.root.wm_attributes("-topmost", self.always_on_top)
        
        # Translucent glass effect background helper
        self.root.config(bg="#123456")
        self.root.wm_attributes("-transparentcolor", "#123456")
        
        # Canvas initialization
        self.canvas = tk.Canvas(
            self.root, 
            width=self.width, 
            height=self.height, 
            bg="#123456", 
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Mouse interactions (drag, snap)
        self.root.x = None
        self.root.y = None
        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drag)
        
        # Double-click for compact bubble toggle
        self.canvas.bind("<Double-Button-1>", self.toggle_compact_mode)
        
        # Right-click context menu
        self.menu = Menu(self.root, tearoff=0)
        self.build_menu()
        self.canvas.bind("<Button-3>", self.show_menu)
        
        # Asynchronous stats thread
        self.running = True
        self.stats_thread = threading.Thread(target=self.stats_collector_loop, daemon=True)
        self.stats_thread.start()
        
        # Redraw loop
        self.redraw_loop()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_config(self):
        config = {
            "x": self.root.winfo_x(),
            "y": self.root.winfo_y(),
            "always_on_top": self.always_on_top,
            "opacity": self.opacity,
            "theme": self.theme_name,
            "compact_mode": self.compact_mode,
            "show_cpu": self.show_cpu,
            "show_ram": self.show_ram,
            "show_gpu": self.show_gpu,
            "show_net": self.show_net
        }
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
        except Exception:
            pass

    def check_gpu_presence(self):
        # 1. Try checking via LibreHardwareMonitor first (if initialized)
        if hasattr(self, 'lhm_initialized') and self.lhm_initialized and self.lhm_computer:
            try:
                for hw in self.lhm_computer.Hardware:
                    if "Gpu" in str(hw.HardwareType):
                        self.gpu_detected = True
                        return
            except Exception:
                pass
        
        # 2. Try WMI Win32_VideoController via PowerShell (runs unelevated)
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            res = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=1
            )
            names = res.decode().strip()
            if names:
                self.gpu_detected = True
                return
        except Exception:
            pass

        # 3. Fallback: Nvidia-smi check
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.check_output(
                ["nvidia-smi", "-L"],
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=1
            )
            self.gpu_detected = True
        except Exception:
            self.gpu_detected = False

    def get_gpu_stats(self):
        if not self.gpu_detected:
            return None, None

        # 1. Try native LibreHardwareMonitor DLL
        if self.lhm_initialized and self.lhm_computer:
            try:
                gpu_usage = None
                gpu_temp = None
                for hw in self.lhm_computer.Hardware:
                    if "Gpu" in str(hw.HardwareType):
                        hw.Update()
                        for s in hw.Sensors:
                            if s.SensorType == self.lhm_sensor_type.Load:
                                if "Core" in s.Name or "GPU" in s.Name or "Load" in s.Name:
                                    if s.Value is not None:
                                        gpu_usage = round(s.Value)
                            elif s.SensorType == self.lhm_sensor_type.Temperature:
                                if "Core" in s.Name or "GPU" in s.Name or "Hot Spot" in s.Name:
                                    if s.Value is not None and s.Value > 0:
                                        gpu_temp = round(s.Value)
                if gpu_usage is not None or gpu_temp is not None:
                    return gpu_usage, gpu_temp
            except Exception:
                pass

        # 2. Try nvidia-smi fallback (for Nvidia GPUs when unelevated)
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            res = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"],
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=1
            )
            parts = res.decode().strip().split(',')
            if len(parts) == 2:
                return int(parts[0].strip()), int(parts[1].strip())
        except Exception:
            pass

        return None, None

    def init_libre_hardware_monitor(self):
        self.lhm_initialized = False
        self.lhm_computer = None
        try:
            import clr
            dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "LibreHardwareMonitorLib.dll")
            if os.path.exists(dll_path):
                clr.AddReference(dll_path)
                from LibreHardwareMonitor.Hardware import Computer, SensorType
                self.lhm_sensor_type = SensorType
                
                # Setup Computer object with CPU, GPU, Motherboard enabled to query shared AMD APU SMU
                self.lhm_computer = Computer()
                self.lhm_computer.IsCpuEnabled = True
                self.lhm_computer.IsGpuEnabled = True
                self.lhm_computer.IsMotherboardEnabled = True
                self.lhm_computer.IsRamEnabled = False
                self.lhm_computer.IsControllerEnabled = False
                self.lhm_computer.IsNetworkEnabled = False
                self.lhm_computer.IsStorageEnabled = False
                
                self.lhm_computer.Open()
                self.lhm_initialized = True
                
                # Re-detect GPU with LHM hardware access
                self.check_gpu_presence()
        except Exception:
            self.lhm_initialized = False

    def query_cpu_temp(self):
        # 1. Try native LibreHardwareMonitorLib direct DLL query (if running as admin)
        if self.lhm_initialized and self.lhm_computer:
            try:
                temps = []
                for hw in self.lhm_computer.Hardware:
                    hw.Update()
                    for s in hw.Sensors:
                        if s.SensorType == self.lhm_sensor_type.Temperature:
                            if "Core" in s.Name or "Package" in s.Name:
                                if s.Value is not None and s.Value > 0:
                                    temps.append(s.Value)
                if temps:
                    return round(max(temps))
            except Exception:
                pass

        # 2. Try WMI query falls back to LibreHardwareMonitor background process (if running separately)
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            res = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", 
                 "(Get-CimInstance -Namespace root/LibreHardwareMonitor -ClassName Sensor -ErrorAction SilentlyContinue | Where-Object {$_.SensorType -eq 'Temperature' -and ($_.Name -like '*Core*' -or $_.Name -like '*Package*')}).Value"],
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=1
            )
            temps = [float(t.strip()) for t in res.decode().strip().split() if t.strip()]
            if temps:
                return round(sum(temps) / len(temps))
        except Exception:
            pass

        # 3. Try standard Windows ACPI thermal zone WMI fallback
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            res = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", 
                 "(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue).CurrentTemperature"],
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=1
            )
            lines = res.decode().strip().split()
            if lines:
                temp_k = float(lines[0])
                temp_c = (temp_k - 2732) / 10.0
                if 0 < temp_c < 150:
                    return round(temp_c)
        except Exception:
            pass
            
        return None

    def calculate_width(self):
        if self.compact_mode:
            return 26
        
        # Calculate dynamic width based on enabled modules and text sizes
        w = 12 # Start padding
        
        modules_visible = []
        if self.show_cpu:
            modules_visible.append("cpu")
        if self.show_ram:
            modules_visible.append("ram")
        if self.show_gpu and self.gpu_detected:
            modules_visible.append("gpu")
        if self.show_net:
            modules_visible.append("net")
            
        for i, mod in enumerate(modules_visible):
            # Add separator width
            if i > 0:
                w += self.label_font.measure(" | ")
                
            if mod == "cpu":
                w += self.label_font.measure("CPU ")
                temp_str = f" {self.cpu_temp}°C" if self.cpu_temp else ""
                w += self.label_font.measure(f"{self.cpu_usage:.0f}%{temp_str}") + 6
                w += 20 # Sparkline width
            elif mod == "ram":
                w += self.label_font.measure("RAM ")
                w += self.label_font.measure(f"{self.ram_usage:.0f}%") + 6
                w += 20 # Sparkline width
            elif mod == "gpu":
                w += self.label_font.measure("GPU ")
                temp_str = f" {self.gpu_temp}°C" if self.gpu_temp else ""
                w += self.label_font.measure(f"{self.gpu_usage:.0f}%{temp_str}") + 6
                w += 20 # Sparkline width
            elif mod == "net":
                w += self.label_font.measure("NET ")
                w += self.label_font.measure(self.net_speed_text)
                
        # End padding
        w += 12
        return max(w, 26)

    def build_menu(self):
        self.menu.delete(0, tk.END)
        
        # Topmost setting
        self.menu.add_checkbutton(
            label="Always on Top", 
            command=self.toggle_always_on_top,
            variable=tk.BooleanVar(value=self.always_on_top)
        )
        
        # Startup setting
        self.menu.add_checkbutton(
            label="Start with Windows",
            command=self.toggle_startup,
            variable=tk.BooleanVar(value=self.check_startup())
        )
        
        self.menu.add_separator()
        
        # Modular views submenu
        views_menu = Menu(self.menu, tearoff=0)
        views_menu.add_checkbutton(label="Show CPU", command=lambda: self.toggle_module("cpu"), variable=tk.BooleanVar(value=self.show_cpu))
        views_menu.add_checkbutton(label="Show RAM", command=lambda: self.toggle_module("ram"), variable=tk.BooleanVar(value=self.show_ram))
        if self.gpu_detected:
            views_menu.add_checkbutton(label="Show GPU", command=lambda: self.toggle_module("gpu"), variable=tk.BooleanVar(value=self.show_gpu))
        views_menu.add_checkbutton(label="Show Network", command=lambda: self.toggle_module("net"), variable=tk.BooleanVar(value=self.show_net))
        self.menu.add_cascade(label="Modules", menu=views_menu)
        
        # Opacity submenu
        opacity_menu = Menu(self.menu, tearoff=0)
        for op in [1.0, 0.85, 0.7, 0.5, 0.3]:
            opacity_menu.add_radiobutton(
                label=f"{int(op * 100)}%", 
                command=lambda val=op: self.set_opacity(val),
                variable=tk.DoubleVar(value=self.opacity),
                value=op
            )
        self.menu.add_cascade(label="Opacity", menu=opacity_menu)
        
        # Themes submenu
        theme_menu = Menu(self.menu, tearoff=0)
        for t_name in THEMES.keys():
            theme_menu.add_radiobutton(
                label=t_name, 
                command=lambda name=t_name: self.set_theme(name),
                variable=tk.StringVar(value=self.theme_name),
                value=t_name
            )
        self.menu.add_cascade(label="Themes", menu=theme_menu)
        
        self.menu.add_separator()
        self.menu.add_command(label="Redetect GPU", command=self.redetect_gpu)
        self.menu.add_command(label="Exit Widget", command=self.exit_app)

    def show_menu(self, event):
        self.build_menu()
        self.menu.post(event.x_root, event.y_root)

    def toggle_always_on_top(self):
        self.always_on_top = not self.always_on_top
        self.root.attributes("-topmost", self.always_on_top)
        self.save_config()

    def set_opacity(self, opacity):
        self.opacity = opacity
        self.root.attributes("-alpha", self.opacity)
        self.save_config()

    def set_theme(self, theme_name):
        self.theme_name = theme_name
        self.save_config()

    def toggle_module(self, module):
        if module == "cpu":
            self.show_cpu = not self.show_cpu
        elif module == "ram":
            self.show_ram = not self.show_ram
        elif module == "gpu":
            self.show_gpu = not self.show_gpu
        elif module == "net":
            self.show_net = not self.show_net
        
        self.save_config()
        self.trigger_resize()

    def redetect_gpu(self):
        self.check_gpu_presence()
        self.trigger_resize()

    def trigger_resize(self):
        self.width = self.calculate_width()
        current_x = self.root.winfo_x()
        current_y = self.root.winfo_y()
        self.root.geometry(f"{self.width}x{self.height}+{current_x}+{current_y}")
        self.canvas.config(width=self.width, height=self.height)
        self.redraw_loop()

    # Startup Shortcut Creation / Removal
    def check_startup(self):
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            res = subprocess.run(
                ["schtasks", "/query", "/tn", "SystemMonitorWidget"],
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
                capture_output=True
            )
            return res.returncode == 0
        except Exception:
            startup_dir = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
            shortcut_path = os.path.join(startup_dir, "SystemMonitorWidget.lnk")
            return os.path.exists(shortcut_path)

    def toggle_startup(self):
        is_enabled = self.check_startup()
        self.set_startup_shortcut(not is_enabled)

    def set_startup_shortcut(self, enable):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        is_admin_mode = is_admin()
        
        if not enable:
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                subprocess.run(
                    ["schtasks", "/delete", "/tn", "SystemMonitorWidget", "/f"],
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            except Exception:
                pass
                
            startup_dir = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
            shortcut_path = os.path.join(startup_dir, "SystemMonitorWidget.lnk")
            if os.path.exists(shortcut_path):
                try:
                    os.remove(shortcut_path)
                except Exception:
                    pass
            return
            
        if is_admin_mode:
            try:
                if getattr(sys, 'frozen', False):
                    target_path = os.path.abspath(sys.executable)
                else:
                    vbs_path = os.path.join(script_dir, "launch.vbs")
                    bat_path = os.path.join(script_dir, "run.bat")
                    with open(vbs_path, "w") as f:
                        f.write('Set WshShell = CreateObject("WScript.Shell")\n')
                        f.write(f'WshShell.Run chr(34) & "{bat_path}" & chr(34), 0, False\n')
                    target_path = vbs_path
                
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                res = subprocess.run(
                    ["schtasks", "/create", "/tn", "SystemMonitorWidget", "/tr", f'"{target_path}"', "/sc", "onlogon", "/rl", "highest", "/f"],
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    capture_output=True
                )
                if res.returncode != 0:
                    raise Exception(res.stderr.decode().strip())
            except Exception as e:
                messagebox.showerror("Error", f"Failed to enable startup task: {e}")
        else:
            try:
                startup_dir = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
                shortcut_path = os.path.join(startup_dir, "SystemMonitorWidget.lnk")
                vbs_path = os.path.join(script_dir, "launch.vbs")
                bat_path = os.path.join(script_dir, "run.bat")
                with open(vbs_path, "w") as f:
                    f.write('Set WshShell = CreateObject("WScript.Shell")\n')
                    f.write(f'WshShell.Run chr(34) & "{bat_path}" & chr(34), 0, False\n')
                    
                powershell_cmd = (
                    f"$WshShell = New-Object -ComObject WScript.Shell; "
                    f"$Shortcut = $WshShell.CreateShortcut('{shortcut_path}'); "
                    f"$Shortcut.TargetPath = '{vbs_path}'; "
                    f"$Shortcut.WorkingDirectory = '{script_dir}'; "
                    f"$Shortcut.WindowStyle = 7; "
                    f"$Shortcut.Save()"
                )
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", powershell_cmd],
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            except Exception as e:
                messagebox.showerror("Error", f"Failed to enable startup shortcut: {e}")

    def toggle_compact_mode(self, event):
        self.compact_mode = not self.compact_mode
        self.trigger_resize()
        self.save_config()

    # Click & Drag movement logic
    def start_drag(self, event):
        self.root.x = event.x
        self.root.y = event.y

    def drag(self, event):
        if self.root.x is None or self.root.y is None:
            return
        dx = event.x - self.root.x
        dy = event.y - self.root.y
        new_x = self.root.winfo_x() + dx
        new_y = self.root.winfo_y() + dy
        
        # Snapping logic to screen boundary
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        snap_margin = 15
        
        if abs(new_x) < snap_margin:
            new_x = 0
        elif abs(new_x + self.width - screen_w) < snap_margin:
            new_x = screen_w - self.width
            
        if abs(new_y) < snap_margin:
            new_y = 0
        elif abs(new_y + self.height - screen_h) < snap_margin:
            new_y = screen_h - self.height
            
        self.root.geometry(f"+{new_x}+{new_y}")

    def stop_drag(self, event):
        self.root.x = None
        self.root.y = None
        self.save_config()

    # Async hardware reading thread (prevents UI lag)
    def stats_collector_loop(self):
        temp_query_counter = 0
        while self.running:
            # CPU Usage
            self.cpu_usage = psutil.cpu_percent(interval=None)
            
            # RAM Usage
            self.ram_usage = psutil.virtual_memory().percent
            
            # CPU Temperature (Polled every 3 seconds to preserve resources)
            if temp_query_counter <= 0:
                self.cpu_temp = self.query_cpu_temp()
                temp_query_counter = 3
            else:
                temp_query_counter -= 1
                
            # Network Traffic
            try:
                curr_sent = psutil.net_io_counters().bytes_sent
                curr_recv = psutil.net_io_counters().bytes_recv
                
                diff_sent = curr_sent - self.prev_net_sent
                diff_recv = curr_recv - self.prev_net_recv
                
                self.prev_net_sent = curr_sent
                self.prev_net_recv = curr_recv
                
                total_bytes = diff_sent + diff_recv
                if total_bytes < 1024:
                    self.net_speed_text = f"↓ {total_bytes} B/s"
                elif total_bytes < 1024 * 1024:
                    self.net_speed_text = f"↓ {total_bytes/1024:.0f} KB/s"
                else:
                    self.net_speed_text = f"↓ {total_bytes/(1024*1024):.1f} MB/s"
            except Exception:
                pass
            
            # GPU statistics (polled every second)
            if self.gpu_detected:
                gpu_u, gpu_t = self.get_gpu_stats()
                if gpu_u is not None:
                    self.gpu_usage = gpu_u
                    self.gpu_temp = gpu_t
            
            time.sleep(1.0)

    # UI Rendering
    def draw_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def draw_sparkline(self, x, y, value, theme):
        # Draw small background track
        self.canvas.create_rectangle(
            x, y, x + 20, y + 4, 
            fill=theme["muted"], 
            outline=""
        )
        # Draw levels
        fill_w = int((min(max(value, 0), 100) / 100) * 20)
        level_color = theme["accent"]
        
        # High load alerts
        if value > 85:
            level_color = "#EF4444"
        elif value > 60:
            level_color = "#F59E0B"
            
        self.canvas.create_rectangle(
            x, y, x + fill_w, y + 4, 
            fill=level_color, 
            outline=""
        )

    def redraw_loop(self):
        if not self.running:
            return
            
        self.canvas.delete("all")
        theme = THEMES.get(self.theme_name, THEMES["Ubuntu Dark"])
        
        # Render dynamic width and background
        self.width = self.calculate_width()
        
        # Redraw the transparent outer shape
        self.draw_rounded_rect(
            0, 0, self.width, self.height, 
            self.corner_radius, 
            fill=theme["bg"], 
            outline=theme["accent"], 
            width=1.2
        )
        
        if self.compact_mode:
            # Render a single pulsing dot reflecting hardware stress
            avg_load = self.cpu_usage
            if self.gpu_detected:
                avg_load = (self.cpu_usage + self.gpu_usage) / 2
                
            dot_color = theme["accent"]
            if avg_load > 85:
                dot_color = "#EF4444"
            elif avg_load > 60:
                dot_color = "#F59E0B"
                
            self.canvas.create_oval(
                9, 8, 17, 16, 
                fill=dot_color, 
                outline=""
            )
        else:
            x = 12 # Left horizontal boundary padding
            
            modules_visible = []
            if self.show_cpu:
                modules_visible.append("cpu")
            if self.show_ram:
                modules_visible.append("ram")
            if self.show_gpu and self.gpu_detected:
                modules_visible.append("gpu")
            if self.show_net:
                modules_visible.append("net")
                
            for i, mod in enumerate(modules_visible):
                # Draw separator if not the first module
                if i > 0:
                    sep = " | "
                    self.canvas.create_text(
                        x, 12, 
                        text=sep, 
                        fill=theme.get("muted_text", "#71717A"), 
                        font=self.label_font, 
                        anchor="w"
                    )
                    x += self.label_font.measure(sep)
                    
                if mod == "cpu":
                    # Label
                    self.canvas.create_text(x, 12, text="CPU ", fill=theme["accent"], font=self.label_font, anchor="w")
                    x += self.label_font.measure("CPU ")
                    
                    # Value
                    temp_str = f" {self.cpu_temp}°C" if self.cpu_temp else ""
                    val_text = f"{self.cpu_usage:.0f}%{temp_str}"
                    self.canvas.create_text(x, 12, text=val_text, fill=theme["text"], font=self.label_font, anchor="w")
                    x += self.label_font.measure(val_text) + 6
                    
                    # Sparkline
                    self.draw_sparkline(x, 10, self.cpu_usage, theme)
                    x += 20
                    
                elif mod == "ram":
                    # Label
                    self.canvas.create_text(x, 12, text="RAM ", fill=theme["accent"], font=self.label_font, anchor="w")
                    x += self.label_font.measure("RAM ")
                    
                    # Value
                    val_text = f"{self.ram_usage:.0f}%"
                    self.canvas.create_text(x, 12, text=val_text, fill=theme["text"], font=self.label_font, anchor="w")
                    x += self.label_font.measure(val_text) + 6
                    
                    # Sparkline
                    self.draw_sparkline(x, 10, self.ram_usage, theme)
                    x += 20
                    
                elif mod == "gpu":
                    # Label
                    self.canvas.create_text(x, 12, text="GPU ", fill=theme["accent"], font=self.label_font, anchor="w")
                    x += self.label_font.measure("GPU ")
                    
                    # Value
                    temp_str = f" {self.gpu_temp}°C" if self.gpu_temp else ""
                    val_text = f"{self.gpu_usage:.0f}%{temp_str}"
                    self.canvas.create_text(x, 12, text=val_text, fill=theme["text"], font=self.label_font, anchor="w")
                    x += self.label_font.measure(val_text) + 6
                    
                    # Sparkline
                    self.draw_sparkline(x, 10, self.gpu_usage, theme)
                    x += 20
                    
                elif mod == "net":
                    # Label
                    self.canvas.create_text(x, 12, text="NET ", fill=theme["accent"], font=self.label_font, anchor="w")
                    x += self.label_font.measure("NET ")
                    
                    # Value
                    val_text = self.net_speed_text
                    self.canvas.create_text(x, 12, text=val_text, fill=theme["text"], font=self.label_font, anchor="w")
                    x += self.label_font.measure(val_text)
                    
        self.root.after(100, self.redraw_loop)

    def exit_app(self):
        self.running = False
        if self.lhm_initialized and self.lhm_computer:
            try:
                self.lhm_computer.Close()
            except Exception:
                pass
        self.save_config()
        self.root.destroy()
        sys.exit(0)

if __name__ == "__main__":
    # Auto UAC elevation check
    if not is_admin() and "--unelevated" not in sys.argv:
        try:
            params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
            if getattr(sys, 'frozen', False):
                result = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
            else:
                script = os.path.abspath(sys.argv[0])
                result = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
            if result > 32:
                sys.exit(0)
        except Exception:
            pass
            
    app = SystemMonitorWidget()
    app.root.mainloop()
