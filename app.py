import json
import os
import queue
import sys
import threading
import time
from datetime import datetime
from urllib.parse import urlparse
from typing import Dict, Optional, List

# GUI Imports
import customtkinter as ctk
from PIL import Image, ImageTk

# Logic Imports
from ping_manager import PingManager, HostStats

# Set theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

APP_TITLE = "Ping Monitor"
APP_SIZE = "1100x700"
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".ping_monitor_settings.json")
DEFAULT_INTERVAL = 1.0


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class HostCard(ctk.CTkFrame):
    """
    A card widget displaying stats for a single host.
    Styled with "OLED Dark" theme and high visibility.
    """
    def __init__(self, master, host: str, remove_callback, *args, **kwargs):
        super().__init__(master, corner_radius=12, fg_color="#0a0a0a", border_width=1, border_color="#222222", *args, **kwargs)
        self.host = host
        self.remove_callback = remove_callback
        
        # Grid layout
        self.grid_columnconfigure(1, weight=1)  # Details expand
        
        # -- 1. Status Indicator (Big Dot) --
        self.status_indicator = ctk.CTkLabel(self, text="●", font=("Arial", 36), text_color="gray")
        self.status_indicator.grid(row=0, column=0, rowspan=2, padx=(15, 10), pady=15, sticky="w")
        
        # -- 2. Host Info --
        self.info_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.info_frame.grid(row=0, column=1, rowspan=2, sticky="nswe", padx=5)
        
        self.lbl_host = ctk.CTkLabel(self.info_frame, text=host, font=("Roboto", 18, "bold"), text_color="#ffffff")
        self.lbl_host.pack(anchor="w")
        
        self.lbl_ip = ctk.CTkLabel(self.info_frame, text="Resolving IP...", font=("Roboto", 14), text_color="#aaaaaa")
        self.lbl_ip.pack(anchor="w")
        
        self.lbl_uptime = ctk.CTkLabel(self.info_frame, text="Uptime: --%", font=("Roboto", 12), text_color="#666666")
        self.lbl_uptime.pack(anchor="w")
        # -- 3. Stats (Sent/Recv/Loss) --
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.grid(row=0, column=2, rowspan=2, padx=20, sticky="e")
        
        self.lbl_sent = ctk.CTkLabel(self.stats_frame, text="S: 0 | R: 0", font=("Roboto Mono", 14), text_color="#dddddd")
        self.lbl_sent.pack(anchor="e")
        
        self.lbl_loss = ctk.CTkLabel(self.stats_frame, text="Loss: 0%", font=("Roboto Mono", 14, "bold"), text_color="#dddddd")
        self.lbl_loss.pack(anchor="e")

        # -- 4. Latency (Big Number) --
        self.lbl_latency = ctk.CTkLabel(self, text="-- ms", font=("Roboto", 28, "bold"), text_color="#ffffff")
        self.lbl_latency.grid(row=0, column=3, rowspan=2, padx=20, sticky="e")

        # -- 5. Delete Button --
        self.btn_delete = ctk.CTkButton(self, text="×", width=35, height=35, 
                                        fg_color="transparent", hover_color="#8b0000", 
                                        font=("Arial", 24), command=self._on_delete, text_color="#555555")
        self.btn_delete.grid(row=0, column=4, rowspan=2, padx=(5, 15), sticky="e")

        # Resolve IP in background
        threading.Thread(target=self._resolve_ip, daemon=True).start()

    def _on_delete(self):
        if self.remove_callback:
            self.remove_callback(self.host)

    def _resolve_ip(self):
        try:
            # simple blocking resolve
            import socket
            ip = socket.gethostbyname(self.host)
            self.lbl_ip.configure(text=ip)
        except:
            self.lbl_ip.configure(text="IP Not Found")

    def update_stats(self, stats: HostStats):
        # 1. Status Color (Brighter Green/Red)
        if stats.last_status == "Up":
            self.status_indicator.configure(text_color="#00ff7f") # SpringGreen
            self.configure(border_color="#004400") # Subtle border hint
        elif stats.last_status == "Down":
            self.status_indicator.configure(text_color="#ff0000") # Pure Red
            self.configure(border_color="#440000") # Subtle border hint
        else:
            self.status_indicator.configure(text_color="gray30")
            self.configure(border_color="#222222")

        # 2. Uptime
        self.lbl_uptime.configure(text=f"Uptime: {stats.uptime_percent():.1f}%")

        # 3. Stats
        self.lbl_sent.configure(text=f"S: {stats.sent} | R: {stats.received}")
        
        loss = stats.loss_percent()
        loss_color = "#dddddd"
        if loss > 0: loss_color = "#ffaa00"
        if loss >= 50: loss_color = "#ff3333"
        self.lbl_loss.configure(text=f"Loss: {loss:.1f}%", text_color=loss_color)

        # 4. Latency
        if stats.last_latency_ms is not None:
            self.lbl_latency.configure(text=f"{stats.last_latency_ms:.1f} ms", text_color="#ffffff")
        else:
            self.lbl_latency.configure(text="-- ms", text_color="#555555")


class GraphPanel(ctk.CTkFrame):
    """
    Bottom panel displaying a multi-line graph for all hosts.
    """
    def __init__(self, master, *args, **kwargs):
        super().__init__(master, fg_color="#050505", corner_radius=0, *args, **kwargs)
        
        self.canvas_height = 200 # Fixed height for now
        self.canvas = ctk.CTkCanvas(self, height=self.canvas_height, bg="#050505", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.colors = ["#00BFFF", "#32CD32", "#FFD700", "#FF4500", "#BA55D3", "#00FA9A", "#FF69B4"]
        self.host_colors = {}
        
    def update_graph(self, stats_map: Dict[str, HostStats]):
        self.canvas.delete("all")
        
        width = self.canvas.winfo_width()
        height = self.canvas_height
        if width < 50: return # not rendered yet

        # Draw grid lines
        self.canvas.create_line(0, height/2, width, height/2, fill="#222222", dash=(2, 4))
        self.canvas.create_line(0, height/4, width, height/4, fill="#222222", dash=(1, 4))
        self.canvas.create_line(0, 3*height/4, width, 3*height/4, fill="#222222", dash=(1, 4))

        # Assign colors
        for i, host in enumerate(stats_map.keys()):
            if host not in self.host_colors:
                self.host_colors[host] = self.colors[i % len(self.colors)]

        # Find global max latency for scaling
        all_values = []
        for s in stats_map.values():
            for _, v in s.history:
                if v is not None: all_values.append(v)
        
        if not all_values: return
        
        max_val = max(all_values)
        if max_val < 50: max_val = 50 # Minimum scale 50ms
        
        # Draw lines for each host
        for host, stats in stats_map.items():
            color = self.host_colors[host]
            history = list(stats.history)
            if len(history) < 2: continue
            
            # X scaling: Fixed window size (HISTORY_MAX points)
            # Or simplified: spread points across width
            # For consistent scrolling, we might want fixed 5px per point?
            # Let's map HISTORY_MAX points to width
            
            step_x = width / (len(history) - 1)
            coords = []
            
            for i, (_, val) in enumerate(history):
                x = i * step_x
                if val is None:
                    coords.append(None)
                else:
                    # Invert Y
                    y = height - ((val / max_val) * (height - 10)) - 5
                    coords.append((x, y))
            
            current_line = []
            for p in coords:
                if p is None:
                    if len(current_line) >= 4:
                        self.canvas.create_line(current_line, fill=color, width=2, smooth=True)
                    current_line = []
                else:
                    current_line.append(p[0])
                    current_line.append(p[1])
            
            if len(current_line) >= 4:
                self.canvas.create_line(current_line, fill=color, width=2, smooth=True)
                
            # Draw legend name at last point if exists
            if coords[-1] is not None:
                lx, ly = coords[-1]
                self.canvas.create_text(lx - 5, ly - 10, text=host, fill=color, anchor="se", font=("Arial", 10))


class PingApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(APP_SIZE)
        
        # Data
        self.manager = PingManager()
        self.hosts_map: Dict[str, HostCard] = {} # host -> CardWidget
        
        # Setup UI
        self._build_layout()
        
        # Load Hosts
        self._load_hosts()
        
        # Start timer
        self.after(100, self._process_queue)
        self.after(500, self._blink_alert) # Global alert blinker
        
        # Handle close
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.alert_state = False

    def _build_layout(self):
        # Grid Layout: 2 rows (Main, Graph), 2 columns (Sidebar, Content)
        self.grid_rowconfigure(0, weight=3) # Main list
        self.grid_rowconfigure(1, weight=1) # Graph panel
        self.grid_columnconfigure(1, weight=1)

        # -- Sidebar --
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#181818")
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar.grid_rowconfigure(5, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="PING\nMonitor", font=ctk.CTkFont(size=26, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 20))

        # Action Buttons
        button_style = {"height": 40, "corner_radius": 8, "font": ("Roboto", 14)}
        self.btn_add = ctk.CTkButton(self.sidebar, text="Add Host", command=self._on_add_host, **button_style)
        self.btn_add.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        self.btn_interval = ctk.CTkButton(self.sidebar, text="Set Interval", command=self._on_set_interval,
                                          fg_color="transparent", border_width=1, border_color="gray40", 
                                          hover_color="#333333", **button_style)
        self.btn_interval.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        
        self.btn_export = ctk.CTkButton(self.sidebar, text="Export CSV", command=self._on_export,
                                          fg_color="transparent", border_width=1, border_color="gray40", 
                                          hover_color="#333333", **button_style)
        self.btn_export.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        self.btn_about = ctk.CTkButton(self.sidebar, text="About / Yvexa", command=self._on_about, 
                                       hover_color="#333333", fg_color="transparent", text_color="#3b8ed0")
        self.btn_about.grid(row=6, column=0, padx=20, pady=(10, 20))
        
        # -- Main Area --
        # Header with Alert
        self.header_frame = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color="#111111")
        self.header_frame.grid(row=0, column=1, sticky="new") # Overlay on top row? No, create a sub-frame
        # Actually easier to put header inside Main Grid
        
        # Let's adjust grid:
        # Row 0: Hosts List (contains header)
        # Row 1: Graph Panel
        
        self.main_container = ctk.CTkFrame(self, fg_color="#000000", corner_radius=0)
        self.main_container.grid(row=0, column=1, sticky="nsew")
        self.main_container.grid_rowconfigure(1, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        # Dashboard Header
        self.dash_head = ctk.CTkFrame(self.main_container, fg_color="transparent", height=60)
        self.dash_head.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        
        self.lbl_title = ctk.CTkLabel(self.dash_head, text="Dashboard", font=("Roboto", 24, "bold"))
        self.lbl_title.pack(side="left")
        
        self.lbl_alert = ctk.CTkLabel(self.dash_head, text="⬤ HEALTHY", font=("Roboto", 16, "bold"), text_color="#00ff7f")
        self.lbl_alert.pack(side="right", padx=10)

        # Host List
        self.scroll_frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent", label_text="")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # -- Graph Panel (Row 1) --
        self.graph_panel = GraphPanel(self)
        self.graph_panel.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)

    def _blink_alert(self):
        # Check if any host is Down
        any_down = False
        stats_snapshot = self.manager.stats_snapshot()
        for stats in stats_snapshot.values():
            if stats.last_status == "Down":
                any_down = True
                break
        
        if any_down:
            self.alert_state = not self.alert_state
            color = "#ff0000" if self.alert_state else "#550000"
            self.lbl_alert.configure(text="⚠️ SYSTEM ALERT", text_color=color)
        else:
            self.lbl_alert.configure(text="⬤ HEALTHY", text_color="#00ff7f")
            
        self.after(500, self._blink_alert)

    def _process_queue(self):
        """Consume all updates from manager queue"""
        # Also limit updates to Graph to avoid lag? For now update every cycle if needed
        # Or update graph every 500ms separately
        
        needs_graph_update = False
        try:
            while True:
                stats = self.manager.update_queue.get_nowait()
                if stats.host in self.hosts_map:
                    self.hosts_map[stats.host].update_stats(stats)
                    needs_graph_update = True
        except queue.Empty:
            pass
        
        if needs_graph_update:
            self.graph_panel.update_graph(self.manager.stats_snapshot())
        
        # Schedule next check
        self.after(100, self._process_queue)

    def _add_host_card(self, host: str):
        if host in self.hosts_map:
            return
        
        card = HostCard(self.scroll_frame, host=host, remove_callback=self._remove_host_request)
        card.grid(row=len(self.hosts_map), column=0, padx=5, pady=5, sticky="ew")
        self.hosts_map[host] = card
        
        # Start monitoring
        self.manager.add_host(host)

    def _remove_host_request(self, host: str):
        if host in self.hosts_map:
            card = self.hosts_map.pop(host)
            card.destroy()
            self.manager.remove_host(host)
            
            # Re-pack grid
            for i, (h, c) in enumerate(self.hosts_map.items()):
                c.grid(row=i, column=0, padx=5, pady=5, sticky="ew")

    # ... Other methods same as before ...
    def _on_add_host(self):
        dialog = ctk.CTkInputDialog(text="Enter Hostname or IP:", title="Add Host")
        host = dialog.get_input()
        if host:
            host = host.strip()
            if "://" in host:
                try:
                    parsed = urlparse(host)
                    host = parsed.netloc or parsed.path
                except: pass
            if host:
                self._add_host_card(host)

    def _on_set_interval(self):
        dialog = ctk.CTkInputDialog(text="Enter Ping Interval (seconds):", title="Settings")
        val = dialog.get_input()
        if val:
            try:
                sec = float(val)
                if sec < 0.2: sec = 0.2
                for h in self.manager.list_hosts():
                    self.manager.update_interval(h, sec)
            except ValueError: pass

    def _on_export(self):
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if not filename: return
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("Host,Status,Last_Latency_ms,Loss_%,Uptime_%\n")
                for h, s in self.manager.stats_snapshot().items():
                    f.write(f"{h},{s.last_status},{s.last_latency_ms},{s.loss_percent()},{s.uptime_percent()}\n")
        except Exception: pass

    def _on_about(self):
        top = ctk.CTkToplevel(self)
        top.title("About")
        top.geometry("400x520")
        top.resizable(False, False)
        top.lift()
        top.focus_force()

        lbl_title = ctk.CTkLabel(top, text="Ping Monitor", font=("Arial", 28, "bold"))
        lbl_title.pack(pady=(30, 10))
        
        lbl_ver = ctk.CTkLabel(top, text="v2.1 Dark Edition", text_color="gray")
        lbl_ver.pack(pady=(0, 20))
        
        lbl_cred = ctk.CTkLabel(top, text="Created by Yvexa", font=("Arial", 18))
        lbl_cred.pack()
        
        lbl_link = ctk.CTkLabel(top, text="Yvexa.dev", font=("Arial", 16), text_color="#3b8ed0", cursor="hand2")
        lbl_link.pack(pady=(0, 20))
        lbl_link.bind("<Button-1>", lambda e: os.startfile("https://yvexa.dev") if os.name == 'nt' else None)

        qr_path = resource_path("qr.png")
        if os.path.exists(qr_path):
            try:
                pil_img = Image.open(qr_path)
                pil_img = pil_img.resize((200, 200), Image.Resampling.LANCZOS)
                img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(200, 200))
                lbl_img = ctk.CTkLabel(top, image=img, text="")
                lbl_img.pack(pady=10)
            except: pass
        else:
            ctk.CTkLabel(top, text="(qr.png not found)").pack()

    def _load_hosts(self):
        path = resource_path("hosts.json")
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    hosts = json.load(f)
                    for h in hosts:
                        self._add_host_card(h)
            except: pass

    def _save_hosts(self):
        hosts = list(self.hosts_map.keys())
        path = resource_path("hosts.json")
        try:
            with open(path, "w") as f:
                json.dump(hosts, f, indent=2)
        except: pass

    def _on_close(self):
        self._save_hosts()
        self.manager.stop_all()
        self.destroy()
        sys.exit(0)


if __name__ == "__main__":
    app = PingApp()
    app.mainloop()
