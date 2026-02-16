import json
import os
import queue
import sys
import threading
import time
from datetime import datetime
from urllib.parse import urlparse
from typing import Dict, Optional, List, TypedDict

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
DEFAULT_INTERVAL = 1.0

def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_user_data_dir() -> str:
    """Get the user data directory for persistence."""
    if os.name == 'nt':
        app_data = os.getenv('APPDATA')
        if app_data:
            path = os.path.join(app_data, "PingMonitor")
        else:
            path = os.path.join(os.path.expanduser("~"), ".ping_monitor")
    else:
        path = os.path.join(os.path.expanduser("~"), ".ping_monitor")
    
    if not os.path.exists(path):
        os.makedirs(path)
    return path

class HostCard(ctk.CTkFrame):
    """
    Compact card widget displaying stats for a single host.
    """
    def __init__(self, master, name: str, target: str, remove_callback, *args, **kwargs):
        super().__init__(master, corner_radius=8, fg_color="#0a0a0a", border_width=2, border_color="#222222", *args, **kwargs)
        self.name = name
        self.target = target
        self.remove_callback = remove_callback
        self.blink_state = False
        
        # Grid layout - Optimized for width
        # Col 0: Status Dot
        # Col 1: Name/Target (Left) - Weight 1
        # Col 2: Min/Max & Last Seen (Center) - Weight 1
        # Col 3: Stats (Center) - Weight 1
        # Col 4: Latency (Right)
        # Col 5: Delete (Far Right)
        
        self.grid_columnconfigure(1, weight=1) 
        self.grid_columnconfigure(2, weight=1)
        self.grid_columnconfigure(3, weight=1)

        # -- 0. Status Indicator --
        self.status_indicator = ctk.CTkLabel(self, text="●", font=("Arial", 28), text_color="gray")
        self.status_indicator.grid(row=0, column=0, rowspan=2, padx=(10, 5), pady=5, sticky="w")
        
        # -- 1. Host Info --
        self.info_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.info_frame.grid(row=0, column=1, rowspan=2, sticky="nswe", padx=5)
        
        self.lbl_name = ctk.CTkLabel(self.info_frame, text=name, font=("Roboto", 16, "bold"), text_color="#ffffff")
        self.lbl_name.pack(anchor="w", pady=(2, 0))
        
        self.lbl_target = ctk.CTkLabel(self.info_frame, text=target, font=("Roboto", 14), text_color="#dddddd")
        self.lbl_target.pack(anchor="w", pady=(0, 2))

        # -- 2. Min/Max & Last Seen --
        self.mid_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.mid_frame.grid(row=0, column=2, rowspan=2, sticky="nswe", padx=5)
        
        self.lbl_minmax = ctk.CTkLabel(self.mid_frame, text="Min: -- | Max: --", font=("Roboto Mono", 12), text_color="#aaaaaa")
        self.lbl_minmax.pack(anchor="center", pady=(2, 0))
        
        self.lbl_last_seen = ctk.CTkLabel(self.mid_frame, text="", font=("Roboto Mono", 12), text_color="#ffaa00")
        self.lbl_last_seen.pack(anchor="center", pady=(0, 2))

        # -- 3. Stats (Compact) --
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.grid(row=0, column=3, rowspan=2, sticky="nswe", padx=10)
        
        self.lbl_sent = ctk.CTkLabel(self.stats_frame, text="S:0 R:0", font=("Roboto Mono", 12), text_color="#dddddd")
        self.lbl_sent.pack(anchor="center")
        
        self.lbl_loss = ctk.CTkLabel(self.stats_frame, text="Loss: 0%", font=("Roboto Mono", 12, "bold"), text_color="#dddddd")
        self.lbl_loss.pack(anchor="center")

        # -- 4. Latency (Current) --
        self.lbl_latency = ctk.CTkLabel(self, text="--ms", font=("Roboto", 24, "bold"), text_color="#ffffff")
        self.lbl_latency.grid(row=0, column=4, rowspan=2, padx=15, sticky="e")

        # -- 5. Delete Button --
        self.btn_delete = ctk.CTkButton(self, text="×", width=25, height=25, 
                                        fg_color="transparent", hover_color="#8b0000", 
                                        font=("Arial", 20), command=self._on_delete, text_color="#555555")
        self.btn_delete.grid(row=0, column=5, rowspan=2, padx=(5, 10), sticky="e")
        
        threading.Thread(target=self._resolve_ip, daemon=True).start()

    def _resolve_ip(self):
        pass

    def _on_delete(self):
        if self.remove_callback:
            self.remove_callback(self.target)

    def update_stats(self, stats: HostStats):
        # 1. Status Color
        if stats.last_status == "Up":
            self.status_indicator.configure(text_color="#00ff7f") 
            self.configure(border_color="#00ff7f", fg_color="#0a0a0a")
            self.lbl_last_seen.configure(text="") # Clear when up
        elif stats.last_status == "Down":
            self.status_indicator.configure(text_color="#ff0000") 
            self.configure(border_color="#ff0000")
            
            # Update Last Seen
            if stats.last_seen_epoch:
                dt = datetime.fromtimestamp(stats.last_seen_epoch)
                self.lbl_last_seen.configure(text=f"Last Seen: {dt.strftime('%H:%M:%S')}")
            else:
                self.lbl_last_seen.configure(text="Last Seen: Never")
        else:
            self.status_indicator.configure(text_color="gray30")
            self.configure(border_color="#222222", fg_color="#0a0a0a")

        # 2. Min/Max
        min_s = f"{stats.latency_min_ms:.0f}" if stats.latency_min_ms is not None else "--"
        max_s = f"{stats.latency_max_ms:.0f}" if stats.latency_max_ms is not None else "--"
        self.lbl_minmax.configure(text=f"Min: {min_s}ms | Max: {max_s}ms")

        # 3. Stats
        self.lbl_sent.configure(text=f"S:{stats.sent} R:{stats.received}")
        loss = stats.loss_percent()
        loss_color = "#dddddd"
        if loss > 0: loss_color = "#ffaa00"
        if loss >= 50: loss_color = "#ff3333"
        self.lbl_loss.configure(text=f"Loss: {loss:.0f}%", text_color=loss_color)

        # 4. Latency
        if stats.last_latency_ms is not None:
            self.lbl_latency.configure(text=f"{stats.last_latency_ms:.0f}ms", text_color="#ffffff")
        else:
            self.lbl_latency.configure(text="--ms", text_color="#555555")

    def blink(self, on: bool):
        if on:
            self.configure(fg_color="#330000") 
        else:
            self.configure(fg_color="#0a0a0a") 


class GraphPanel(ctk.CTkFrame):
    """
    Bottom panel displaying a multi-line graph for all hosts.
    """
    def __init__(self, master, *args, **kwargs):
        super().__init__(master, fg_color="#050505", corner_radius=0, *args, **kwargs)
        
        self.canvas_height = 250 
        self.canvas = ctk.CTkCanvas(self, height=self.canvas_height, bg="#050505", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=0, pady=0) 
        
        self.colors = ["#00BFFF", "#32CD32", "#FFD700", "#FF4500", "#BA55D3", "#00FA9A", "#FF69B4"]
        self.host_colors = {}
        
    def update_graph(self, stats_map: Dict[str, HostStats], host_aliases: Dict[str, str]):
        self.canvas.delete("all")
        
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height() if self.canvas.winfo_height() > 10 else self.canvas_height
        if width < 50: return 

        # Draw grid lines
        self.canvas.create_line(0, height/2, width, height/2, fill="#222222", dash=(2, 4))
        self.canvas.create_line(0, height/4, width, height/4, fill="#222222", dash=(1, 4))
        self.canvas.create_line(0, 3*height/4, width, 3*height/4, fill="#222222", dash=(1, 4))

        # Check bounds
        all_values = []
        for s in stats_map.values():
            for _, v in s.history:
                if v is not None: 
                    all_values.append(v)
        
        max_val = 100 
        if all_values:
            actual_max = max(all_values)
            if actual_max > max_val: max_val = actual_max
        
        # Legend drawing area (Top Left) - HORIZONTAL
        legend_x = 10
        legend_y = 10
        legend_spacing = 15 
        
        # Draw lines
        sorted_hosts = sorted(stats_map.keys())
        current_legend_x = legend_x
        
        for i, host in enumerate(sorted_hosts):
            if host not in self.host_colors:
                self.host_colors[host] = self.colors[i % len(self.colors)]
            color = self.host_colors[host]
            
            # 1. Draw Legend Item
            alias = host_aliases.get(host, host)
            text_id = self.canvas.create_text(current_legend_x, legend_y, text=f"■ {alias}", fill=color, anchor="w", font=("Arial", 11, "bold"))
            
            bbox = self.canvas.bbox(text_id)
            if bbox:
                text_width = bbox[2] - bbox[0]
                current_legend_x += text_width + legend_spacing

            # 2. Draw Line
            stats = stats_map[host]
            history = list(stats.history)
            if len(history) < 2: continue
            
            step_x = width / (len(history) - 1)
            coords = []
            
            for j, (_, val) in enumerate(history):
                x = j * step_x
                if val is None:
                    y = height 
                else:
                    y = height - ((val / max_val) * (height - 30)) - 10 
                coords.append((x, y))
            
            points = []
            for x, y in coords:
                points.append(x)
                points.append(y)
            
            if len(points) >= 4:
                self.canvas.create_line(points, fill=color, width=2, smooth=True)


class PingApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(APP_SIZE)
        
        # Data
        self.manager = PingManager()
        self.hosts_map: Dict[str, HostCard] = {} 
        self.host_aliases: Dict[str, str] = {}
        
        self.toplevel_add_host = None
        self.toplevel_about = None
        self.sidebar_expanded = True
        
        # Setup UI
        self._build_layout()
        
        # Load Hosts
        self._load_hosts()
        
        # Start timer
        self.after(100, self._process_queue)
        self.after(500, self._blink_logic)
        
        # Handle close
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.alert_state = False

    def _build_layout(self):
        self.grid_rowconfigure(0, weight=1) 
        self.grid_columnconfigure(1, weight=1)

        # -- Sidebar --
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#181818")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False) 
        self.sidebar.grid_rowconfigure(6, weight=1) 
        
        # Sidebar Content
        self.sidebar_content = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sidebar_content.pack(fill="both", expand=True)
        
        self.btn_toggle = ctk.CTkButton(self.sidebar_content, text="☰", width=40, command=self._toggle_sidebar, fg_color="transparent")
        self.btn_toggle.pack(anchor="w", padx=10, pady=10)
        
        self.lbl_logo = ctk.CTkLabel(self.sidebar_content, text="PING\nMonitor", font=ctk.CTkFont(size=26, weight="bold"))
        self.lbl_logo.pack(pady=(10, 20))

        # Buttons
        btn_style = {"height": 40, "corner_radius": 8, "font": ("Roboto", 14)}
        
        self.btn_add = ctk.CTkButton(self.sidebar_content, text="Add Host", command=self._on_add_host_dialog, **btn_style)
        self.btn_add.pack(padx=20, pady=10, fill="x")

        self.btn_interval = ctk.CTkButton(self.sidebar_content, text="Set Interval", command=self._on_set_interval,
                                          fg_color="transparent", border_width=1, border_color="gray40", 
                                          hover_color="#333333", **btn_style)
        self.btn_interval.pack(padx=20, pady=10, fill="x")
        
        self.btn_export = ctk.CTkButton(self.sidebar_content, text="Export CSV", command=self._on_export,
                                          fg_color="transparent", border_width=1, border_color="gray40", 
                                          hover_color="#333333", **btn_style)
        self.btn_export.pack(padx=20, pady=10, fill="x")

        # Spacer
        self.btn_about = ctk.CTkButton(self.sidebar_content, text="About", command=self._on_about, 
                                       hover_color="#333333", fg_color="#222222", border_width=1, border_color="#333333", text_color="#3b8ed0", **btn_style)
        self.btn_about.pack(side="bottom", padx=20, pady=20, fill="x")
        
        # -- Main Content Area --
        self.main_area = ctk.CTkFrame(self, fg_color="#000000", corner_radius=0)
        self.main_area.grid(row=0, column=1, sticky="nsew")
        
        # Sub-Grid
        self.main_area.grid_rowconfigure(1, weight=1) 
        self.main_area.grid_columnconfigure(0, weight=1)

        # 1. Header
        self.header_frame = ctk.CTkFrame(self.main_area, fg_color="transparent", height=50)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=5)
        
        self.lbl_title = ctk.CTkLabel(self.header_frame, text="Dashboard", font=("Roboto", 24, "bold"))
        self.lbl_title.pack(side="left")
        
        self.lbl_status = ctk.CTkLabel(self.header_frame, text="⬤ HEALTHY", font=("Roboto", 16, "bold"), text_color="#00ff7f")
        self.lbl_status.pack(side="right", padx=10)

        # 2. Host List
        self.scroll_frame = ctk.CTkScrollableFrame(self.main_area, fg_color="transparent", label_text="")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 0))
        self.scroll_frame.grid_columnconfigure(0, weight=1)
        
        # 3. Warning Banner (between List and Graph)
        self.warning_banner = ctk.CTkFrame(self.main_area, fg_color="#ff0000", height=0, corner_radius=0)
        self.warning_banner.grid(row=2, column=0, sticky="ew")
        self.lbl_warning = ctk.CTkLabel(self.warning_banner, text="⚠️ SYSTEM ALERT: ONE OR MORE HOSTS DOWN", font=("Roboto", 18, "bold"), text_color="white")
        self.lbl_warning.pack(pady=5)
        self.warning_banner.grid_remove() # Hide initially

        # 4. Graph Panel (Bottom)
        self.graph_panel = GraphPanel(self.main_area)
        self.graph_panel.grid(row=3, column=0, sticky="ew", padx=0, pady=0)

    def _toggle_sidebar(self):
        self.lbl_logo.pack_forget()
        self.btn_add.pack_forget()
        self.btn_interval.pack_forget()
        self.btn_export.pack_forget()
        self.btn_about.pack_forget()
        
        if self.sidebar_expanded:
            self.sidebar.configure(width=50)
            self.sidebar_expanded = False
        else:
            self.sidebar.configure(width=220)
            self.sidebar_expanded = True
            
            self.lbl_logo.pack(pady=(10, 20), after=self.btn_toggle)
            self.btn_add.pack(padx=20, pady=10, fill="x", after=self.lbl_logo)
            self.btn_interval.pack(padx=20, pady=10, fill="x", after=self.btn_add)
            self.btn_export.pack(padx=20, pady=10, fill="x", after=self.btn_interval)
            self.btn_about.pack(side="bottom", padx=20, pady=20, fill="x")

    def _blink_logic(self):
        self.alert_state = not self.alert_state
        any_down = False
        stats_snapshot = self.manager.stats_snapshot()
        
        for target, stats in stats_snapshot.items():
            if stats.last_status == "Down":
                any_down = True
                if target in self.hosts_map:
                    self.hosts_map[target].blink(self.alert_state)
            else:
                if target in self.hosts_map: 
                    self.hosts_map[target].blink(False)
        
        if any_down:
            self.warning_banner.grid() 
            banner_bg = "#ff0000" if self.alert_state else "#880000"
            self.warning_banner.configure(fg_color=banner_bg)
            self.lbl_status.configure(text="CRITICAL", text_color="#ff0000")
        else:
            self.warning_banner.grid_remove() 
            self.lbl_status.configure(text="⬤ HEALTHY", text_color="#00ff7f")
            
        self.after(500, self._blink_logic)

    def _process_queue(self):
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
            self.graph_panel.update_graph(self.manager.stats_snapshot(), self.host_aliases)
        
        self.after(100, self._process_queue)

    def _add_host_card(self, target: str, name: str):
        if target in self.hosts_map:
            return
        
        card = HostCard(self.scroll_frame, name=name, target=target, remove_callback=self._remove_host_request)
        card.grid(row=len(self.hosts_map), column=0, padx=5, pady=2, sticky="ew")
        self.hosts_map[target] = card
        self.host_aliases[target] = name
        
        self.manager.add_host(target)

    def _remove_host_request(self, target: str):
        if target in self.hosts_map:
            card = self.hosts_map.pop(target)
            card.destroy()
            self.manager.remove_host(target)
            self.host_aliases.pop(target, None)
            
            for i, (h, c) in enumerate(self.hosts_map.items()):
                c.grid(row=i, column=0, padx=5, pady=2, sticky="ew")

    def _on_add_host_dialog(self):
        if self.toplevel_add_host is None or not self.toplevel_add_host.winfo_exists():
            self.toplevel_add_host = ctk.CTkToplevel(self)
            self.toplevel_add_host.title("Add Host")
            self.toplevel_add_host.geometry("300x240") 
            self.toplevel_add_host.resizable(False, False)
            self.toplevel_add_host.lift()
            self.toplevel_add_host.focus_force()
            self.toplevel_add_host.attributes("-topmost", True) 
            
            ctk.CTkLabel(self.toplevel_add_host, text="Display Name:").pack(pady=(10, 0))
            entry_name = ctk.CTkEntry(self.toplevel_add_host)
            entry_name.pack(pady=5)
            
            ctk.CTkLabel(self.toplevel_add_host, text="Hostname / IP:").pack(pady=(10, 0))
            entry_target = ctk.CTkEntry(self.toplevel_add_host)
            entry_target.pack(pady=5)
            
            def _confirm():
                name = entry_name.get().strip()
                target = entry_target.get().strip()
                if target:
                    if not name: name = target
                    if "://" in target:
                        try:
                            p = urlparse(target)
                            target = p.netloc or p.path
                        except: pass
                    
                    self._add_host_card(target, name)
                    self.toplevel_add_host.destroy()
                    self.toplevel_add_host = None
                    
            ctk.CTkButton(self.toplevel_add_host, text="Add", command=_confirm).pack(pady=20)
        else:
            self.toplevel_add_host.lift()
            self.toplevel_add_host.focus_force()

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
                f.write("Name,Target,Status,Last_Latency_ms,Loss_%\n")
                for target, s in self.manager.stats_snapshot().items():
                    name = self.host_aliases.get(target, target)
                    f.write(f"{name},{target},{s.last_status},{s.last_latency_ms},{s.loss_percent()}\n")
        except Exception: pass

    def _on_about(self):
        if self.toplevel_about is None or not self.toplevel_about.winfo_exists():
            self.toplevel_about = ctk.CTkToplevel(self)
            self.toplevel_about.title("About")
            self.toplevel_about.geometry("400x520")
            self.toplevel_about.resizable(False, False)
            self.toplevel_about.lift()
            self.toplevel_about.focus_force()
            self.toplevel_about.attributes("-topmost", True) 

            lbl_title = ctk.CTkLabel(self.toplevel_about, text="Ping Monitor", font=("Arial", 28, "bold"))
            lbl_title.pack(pady=(30, 10))
            
            lbl_ver = ctk.CTkLabel(self.toplevel_about, text="v2.3 Platinum", text_color="gray")
            lbl_ver.pack(pady=(0, 20))
            
            lbl_cred = ctk.CTkLabel(self.toplevel_about, text="Created by Yvexa", font=("Arial", 18))
            lbl_cred.pack()
            
            lbl_link = ctk.CTkLabel(self.toplevel_about, text="Yvexa.dev", font=("Arial", 16), text_color="#3b8ed0", cursor="hand2")
            lbl_link.pack(pady=(0, 20))
            lbl_link.bind("<Button-1>", lambda e: os.startfile("https://yvexa.dev") if os.name == 'nt' else None)

            qr_path = resource_path("qr.png")
            if os.path.exists(qr_path):
                try:
                    pil_img = Image.open(qr_path)
                    pil_img = pil_img.resize((200, 200), Image.Resampling.LANCZOS)
                    img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(200, 200))
                    lbl_img = ctk.CTkLabel(self.toplevel_about, image=img, text="")
                    lbl_img.pack(pady=10)
                except: pass
            else:
                ctk.CTkLabel(self.toplevel_about, text="(qr.png not found)").pack()
        else:
            self.toplevel_about.lift()
            self.toplevel_about.focus_force()

    def _load_hosts(self):
        # 1. Try Persistence dir
        data_dir = get_user_data_dir()
        path = os.path.join(data_dir, "hosts.json")
        
        # 2. If not found, try local resource fallback (migration)
        if not os.path.exists(path):
            local_path = resource_path("hosts.json")
            if os.path.exists(local_path):
                try:
                    with open(local_path, "r") as f:
                        data = json.load(f)
                    # Migrate to persistence
                    with open(path, "w") as f:
                        json.dump(data, f, indent=2)
                except: pass

        # 3. Load from persistence
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, str):
                            self._add_host_card(item, item)
                        elif isinstance(item, dict):
                            self._add_host_card(item.get("target"), item.get("name", item.get("target")))
            except: pass

    def _save_hosts(self):
        data = []
        for target in self.hosts_map.keys():
            name = self.host_aliases.get(target, target)
            data.append({"name": name, "target": target})
        
        data_dir = get_user_data_dir()
        path = os.path.join(data_dir, "hosts.json")
        
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except: pass

    def _on_close(self):
        self._save_hosts()
        self.manager.stop_all()
        self.destroy()
        sys.exit(0)


if __name__ == "__main__":
    app = PingApp()
    app.mainloop()
