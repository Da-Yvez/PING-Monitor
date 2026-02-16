import json
import os
import queue
import sys
import time
from datetime import datetime
from urllib.parse import urlparse
import base64
import tkinter as tk
from tkinter import messagebox, simpledialog
from tkinter import ttk

from ping_manager import PingManager, HostStats


APP_TITLE = "Ping Monitor"
DEFAULT_INTERVAL_SECONDS = 1.0
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".ping_monitor_settings.json")


def resource_path(*parts: str) -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, *parts)


HOSTS_FILE = resource_path("hosts.json")


class PingApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        # Window sizing restored from settings later
        self.geometry("800x420")

        # Embedded tiny PNG used for window icon so bundled exe has an icon without extra files
        ICON_PNG = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
        )
        try:
            img = tk.PhotoImage(data=base64.b64decode(ICON_PNG))
            # Keep a reference alive
            self._icon_image = img
            try:
                self.iconphoto(False, img)
            except Exception:
                pass
        except Exception:
            pass

        self.manager = PingManager()
        # Which hosts are shown in the graph (populated as hosts are loaded)
        self._graph_visible = {}
        # Legend checkbox vars
        self._legend_vars = {}
        # Graph show/hide var
        self._show_graph_var = tk.BooleanVar(value=True)
        self._build_ui()
        self._build_menu()

        self._settings = self._load_settings()
        hosts = self._load_hosts()
        for host in hosts:
            self.manager.add_host(host, interval_seconds=self._settings.get("default_interval", DEFAULT_INTERVAL_SECONDS))
            # default to visible in graph
            self._graph_visible[host] = True
            self._ensure_tree_item(host)

        # Restore window size if present
        geom = self._settings.get("window_geometry")
        if isinstance(geom, str) and geom:
            try:
                self.geometry(geom)
            except Exception:
                pass

        self.after(100, self._drain_updates)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        self._apply_dark_theme()
        outer = ttk.Frame(self)
        outer.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        controls = ttk.Frame(outer)
        controls.pack(fill=tk.X, pady=(0, 8))

        self.host_var = tk.StringVar()
        host_entry = ttk.Entry(controls, textvariable=self.host_var)
        host_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        host_entry.bind("<Return>", lambda e: self._on_add())

        add_btn = ttk.Button(controls, text="Add", command=self._on_add)
        add_btn.pack(side=tk.LEFT, padx=(8, 0))

        remove_btn = ttk.Button(controls, text="Remove Selected", command=self._on_remove)
        remove_btn.pack(side=tk.LEFT, padx=(8, 0))

        edit_btn = ttk.Button(controls, text="Set Interval", command=self._on_set_interval)
        edit_btn.pack(side=tk.LEFT, padx=(8, 0))

        # Small health indicator on the right that pulses when any host is Down
        self._health_canvas = tk.Canvas(controls, width=26, height=26, highlightthickness=0, bg=self.cget("bg"))
        self._health_canvas.pack(side=tk.RIGHT, padx=(8, 0))
        # Draw a circle
        self._health_dot = self._health_canvas.create_oval(4, 4, 22, 22, fill="#7ee787", outline="")
        self._health_pulse_phase = 0
        self._any_down = False
        self.after(120, self._health_pulse_step)

        columns = ("status_icon", "host", "status", "latency", "avg", "min", "max", "sent", "received", "loss", "uptime", "last_seen", "message")

        # Table frame (top) holds the tree and its scrollbar so graph can sit under it
        table_frame = ttk.Frame(outer)
        table_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=14)
        self.tree.heading("status_icon", text="")
        self.tree.heading("host", text="Host")
        self.tree.heading("status", text="Status")
        self.tree.heading("latency", text="Latency (ms)")
        self.tree.heading("avg", text="Avg (ms)")
        self.tree.heading("min", text="Min (ms)")
        self.tree.heading("max", text="Max (ms)")
        self.tree.heading("sent", text="Sent")
        self.tree.heading("received", text="Recv")
        self.tree.heading("loss", text="Loss %")
        self.tree.heading("uptime", text="Uptime %")
        self.tree.heading("last_seen", text="Last Seen")
        self.tree.heading("message", text="Last Message")

        self.tree.column("status_icon", width=18, anchor=tk.CENTER)
        self.tree.column("host", width=160, anchor=tk.W)
        self.tree.column("status", width=70, anchor=tk.CENTER)
        self.tree.column("latency", width=90, anchor=tk.E)
        self.tree.column("avg", width=90, anchor=tk.E)
        self.tree.column("min", width=90, anchor=tk.E)
        self.tree.column("max", width=90, anchor=tk.E)
        self.tree.column("sent", width=60, anchor=tk.E)
        self.tree.column("received", width=60, anchor=tk.E)
        self.tree.column("loss", width=70, anchor=tk.E)
        self.tree.column("uptime", width=80, anchor=tk.E)
        self.tree.column("last_seen", width=140, anchor=tk.W)
        self.tree.column("message", width=300, anchor=tk.W)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.LEFT, fill=tk.Y)

        status_bar = ttk.Label(self, text="Enter a host/IP and click Add.")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        # keep a reference for transient messages
        self._status_label = status_bar

        # Treeview row tag styles
        self.tree.tag_configure("up", foreground="#7ee787")      # brighter green
        self.tree.tag_configure("down", foreground="#ff7b72")    # brighter red
        self.tree.tag_configure("unknown", foreground="#abb2bf") # gray
        # Blink state - bright red background when blinking
        self.tree.tag_configure("blink", background="#cc0000")

        # Deselect when clicking blank area
        self.tree.bind("<Button-1>", self._on_tree_click_blank, add=True)
        # Double click copies host to clipboard for convenience
        self.tree.bind("<Double-1>", self._on_tree_double)

        # Zebra stripes for readability
        self.tree.tag_configure("oddrow", background="#202020")
        self.tree.tag_configure("evenrow", background="#1a1a1a")

        # Alert bar (hidden normally) that blinks bright red when any host is down
        self._alert_bar = tk.Label(self, text="⚠ ALERT: One or more hosts are DOWN ⚠", 
                                  bg="#5a1a1a", fg="#ffffff", font=("Helvetica", 14, "bold"),
                                  padx=16, pady=6)
        # Graph area under the table showing recent latency histories (5-minute window)
        graph_section = ttk.Frame(outer)
        graph_section.pack(fill=tk.X, pady=(8, 0))

        # Legend frame immediately above the graph, with dark background for visibility
        legend_container = ttk.Frame(graph_section, style="Dark.TFrame")
        legend_container.pack(fill=tk.X, padx=2, pady=(0, 4))
        self.legend_frame = ttk.Frame(legend_container)
        self.legend_frame.pack(fill=tk.X, pady=4)

        # The graph canvas itself
        self.graph_frame = ttk.Frame(graph_section)
        self.graph_frame.pack(fill=tk.X)
        # Make it larger for clearer analysis
        self.graph_canvas = tk.Canvas(self.graph_frame, height=260, bg="#0f0f0f", highlightthickness=0)
        self.graph_canvas.pack(fill=tk.BOTH, expand=True)
        # color palette for hosts
        self._graph_colors = ["#7ee787", "#ff7b72", "#ffd66b", "#8ad4ff", "#d39bff", "#9be79b", "#ff9fbf", "#c0c0c0", "#6ad3a6", "#ffa36a"]
        # schedule periodic graph updates
        self.after(800, self._update_graph)
        # schedule alert blink step
        self._alert_blink_state = False
        self.after(400, self._alert_blink_step)

        # (ui bindings already set above)

    def _apply_dark_theme(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        bg = "#1e1e1e"
        fg = "#e6e6e6"
        subtle = "#2a2a2a"
        accent = "#3a3a3a"
        sel_bg = "#264f78"
        sel_fg = "#ffffff"

        # Base styles
        self.configure(bg=bg)
        style.configure("TFrame", background=bg)
        style.configure("Dark.TFrame", background="#0f0f0f")  # Darker background for legend
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("Dark.TLabel", background="#0f0f0f", foreground="#e6e6e6")  # Labels on dark background
        style.configure("TButton", background=subtle, foreground=fg, relief="flat", padding=6)
        style.map("TButton",
                  background=[("active", accent)],
                  relief=[("pressed", "sunken")])

        # Entry
        style.configure("TEntry", fieldbackground=subtle, foreground=fg)

        # Treeview
        style.configure("Treeview",
                        background=bg,
                        foreground=fg,
                        fieldbackground=bg,
                        rowheight=22,
                        bordercolor=subtle,
                        borderwidth=0)
        style.map("Treeview",
                  background=[("selected", sel_bg)],
                  foreground=[("selected", sel_fg)])
        style.configure("Treeview.Heading",
                        background=subtle,
                        foreground=fg,
                        relief="flat")
        style.map("Treeview.Heading",
                  background=[("active", accent)])

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0, bg="#1e1e1e", fg="#e6e6e6", activebackground="#333333", activeforeground="#ffffff")
        file_menu.add_command(label="Export CSV", command=self._on_export_csv)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        # View menu to toggle columns and graph
        view_menu = tk.Menu(menubar, tearoff=0, bg="#1e1e1e", fg="#e6e6e6", activebackground="#333333", activeforeground="#ffffff")
        self._column_vars = {}
        for col, label in [("avg", "Avg (ms)"), ("min", "Min (ms)"), ("max", "Max (ms)"), ("uptime", "Uptime %"), ("message", "Last Message")]:
            var = tk.BooleanVar(value=True)
            self._column_vars[col] = var
            view_menu.add_checkbutton(label=label, variable=var, command=lambda c=col: self._toggle_column(c))

        # Graph controls
        view_menu.add_separator()
        view_menu.add_checkbutton(label="Show Graph", variable=self._show_graph_var, command=self._toggle_graph)
        view_menu.add_command(label="Select Graph Hosts...", command=self._select_graph_hosts)
        menubar.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0, bg="#1e1e1e", fg="#e6e6e6", activebackground="#333333", activeforeground="#ffffff")
        help_menu.add_command(label="About", command=self._on_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.config(menu=menubar)

    def _toggle_graph(self) -> None:
        # Show or hide the graph area
        try:
            visible = self._show_graph_var.get()
            if hasattr(self, "graph_frame"):
                if visible:
                    self.graph_frame.pack(fill=tk.X, pady=(8, 0))
                else:
                    self.graph_frame.pack_forget()
        except Exception:
            pass

    def _select_graph_hosts(self) -> None:
        # Simple dialog to let user choose which hosts are visible on the graph
        hosts = sorted(self._get_all_tree_hosts())
        if not hosts:
            messagebox.showinfo("Select Hosts", "No hosts available.")
            return
        dlg = tk.Toplevel(self)
        dlg.title("Select Graph Hosts")
        dlg.transient(self)
        dlg.grab_set()
        checks: dict[str, tk.BooleanVar] = {}
        for h in hosts:
            var = tk.BooleanVar(value=self._graph_visible.get(h, True))
            checks[h] = var
            cb = ttk.Checkbutton(dlg, text=h, variable=var)
            cb.pack(anchor=tk.W, padx=8, pady=2)

        def _apply():
            for h, v in checks.items():
                self._graph_visible[h] = bool(v.get())
            dlg.destroy()

        btn = ttk.Button(dlg, text="Apply", command=_apply)
        btn.pack(pady=8)

    def _on_add(self) -> None:
        raw = self.host_var.get().strip()
        host = self._normalize_host(raw)
        if not host:
            return
        if host in self._get_all_tree_hosts():
            return
        self.manager.add_host(host, interval_seconds=self._settings.get("default_interval", DEFAULT_INTERVAL_SECONDS))
        self._ensure_tree_item(host)
        self.host_var.set("")
        self._save_hosts()

    def _on_remove(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        for item_id in selected:
            host = self.tree.set(item_id, "host")
            self.manager.remove_host(host)
            self.tree.delete(item_id)
            # remove from graph visibility map
            if host in self._graph_visible:
                del self._graph_visible[host]
        try:
            # rebuild legend after removal
            self._rebuild_legend(list(self._graph_visible.keys()), {h: self._graph_colors[idx % len(self._graph_colors)] for idx, h in enumerate(self._graph_visible)})
        except Exception:
            pass
        self._save_hosts()

    def _get_all_tree_hosts(self) -> set[str]:
        hosts: set[str] = set()
        for iid in self.tree.get_children(""):
            hosts.add(self.tree.set(iid, "host"))
        return hosts

    def _ensure_tree_item(self, host: str) -> None:
        # If not present, insert an empty row for the host
        for iid in self.tree.get_children(""):
            if self.tree.set(iid, "host") == host:
                return
        idx = len(self.tree.get_children(""))
        row_tag = "oddrow" if idx % 2 else "evenrow"
        self.tree.insert("", tk.END, values=("", host, "...", "", "", "", "", "", "", "", "", "", ""), tags=("unknown", row_tag))
        # Ensure graph visibility entry exists and update legend
        if host not in self._graph_visible:
            self._graph_visible[host] = True
        try:
            self._rebuild_legend(list(self._graph_visible.keys()), {h: self._graph_colors[idx % len(self._graph_colors)] for idx, h in enumerate(self._graph_visible)})
        except Exception:
            pass

    def _update_tree_with_stats(self, stats: HostStats) -> None:
        for iid in self.tree.get_children(""):
            if self.tree.set(iid, "host") == stats.host:
                last_seen_str = ""
                if stats.last_seen_epoch:
                    dt = datetime.fromtimestamp(stats.last_seen_epoch)
                    last_seen_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                latency_str = f"{stats.last_latency_ms:.1f}" if stats.last_latency_ms is not None else ""
                avg_str = f"{stats.avg_latency_ms():.1f}" if stats.avg_latency_ms() is not None else ""
                min_str = f"{stats.latency_min_ms:.1f}" if stats.latency_min_ms is not None else ""
                max_str = f"{stats.latency_max_ms:.1f}" if stats.latency_max_ms is not None else ""
                loss_str = f"{stats.loss_percent():.0f}"
                uptime_str = f"{stats.uptime_percent():.0f}"
                icon = "●" if stats.last_status == "Up" else ("○" if stats.last_status == "Down" else "·")
                # Sound alert on transition to Down
                previous_status = self.tree.set(iid, "status")
                if previous_status != "Down" and stats.last_status == "Down":
                    try:
                        self.bell()
                    except Exception:
                        pass
                self.tree.item(iid, values=(
                    icon,
                    stats.host,
                    stats.last_status,
                    latency_str,
                    avg_str,
                    min_str,
                    max_str,
                    str(stats.sent),
                    str(stats.received),
                    loss_str,
                    uptime_str,
                    last_seen_str,
                    stats.last_message,
                ))
                tag = "up" if stats.last_status == "Up" else ("down" if stats.last_status == "Down" else "unknown")
                self.tree.item(iid, tags=(tag,))
                break
        # Update overall health state for the pulsing indicator
        any_down = False
        for iid in self.tree.get_children(""):
            if self.tree.set(iid, "status") == "Down":
                any_down = True
                break
        self._any_down = any_down

    def _drain_updates(self) -> None:
        # Pull all available updates without blocking; apply latest per-host
        latest_by_host: dict[str, HostStats] = {}
        try:
            while True:
                stats = self.manager.update_queue.get_nowait()
                latest_by_host[stats.host] = stats
        except queue.Empty:
            pass

        for stats in latest_by_host.values():
            self._update_tree_with_stats(stats)

        self.after(200, self._drain_updates)

    def _update_graph(self) -> None:
        try:
            stats_map = self.manager.stats_snapshot()
            self._draw_graph(stats_map)
        except Exception:
            pass
        finally:
            # refresh more slowly than table updates
            self.after(800, self._update_graph)

    def _draw_graph(self, stats_map: dict[str, HostStats]) -> None:
        # Clear canvas
        try:
            c = self.graph_canvas
            c.delete("all")
            w = c.winfo_width() or c.winfo_reqwidth() or 800
            h = c.winfo_height() or c.winfo_reqheight() or 260

            padding = 6
            left_margin = 60
            bottom_margin = 28
            top_margin = 8
            inner_w = max(40, w - left_margin - padding)
            inner_h = max(40, h - top_margin - bottom_margin)

            hosts = list(stats_map.keys())
            # filter hosts by visibility
            visible_hosts = [h for h in hosts if self._graph_visible.get(h, True)]
            # map host to a color index
            color_map: dict[str, str] = {}
            for idx, host in enumerate(visible_hosts):
                color_map[host] = self._graph_colors[idx % len(self._graph_colors)]

            # Consider only last 5 minutes
            now_ts = time.time()
            window_start = now_ts - 300.0

            # collect global max latency inside window to scale y-axis (default 200ms)
            global_max = 200.0
            for h in visible_hosts:
                s = stats_map.get(h)
                if not s:
                    continue
                for (ts, v) in s.history:
                    if ts >= window_start and v is not None and v > global_max:
                        global_max = float(v)

            # draw horizontal grid lines and Y axis labels
            for i in range(5):
                frac = i / 4.0
                y = top_margin + frac * inner_h
                c.create_line(left_margin, y, left_margin + inner_w, y, fill="#1a1a1a")
                # label
                val = int((1.0 - frac) * global_max)
                c.create_text(left_margin - 8, y, text=f"{val} ms", anchor=tk.E, fill="#c0c0c0", font=(None, 9))

            # Cache the current host colors
            current_colors = {h: self._graph_colors[idx % len(self._graph_colors)] for idx, h in enumerate(visible_hosts)}
            # Only rebuild legend if hosts or colors changed
            if not hasattr(self, '_last_legend_state') or \
               self._last_legend_state != (tuple(visible_hosts), tuple(current_colors.items())):
                try:
                    self._rebuild_legend(visible_hosts, current_colors)
                    self._last_legend_state = (tuple(visible_hosts), tuple(current_colors.items()))
                except Exception:
                    pass

            # draw each host history as a time-based polyline within the 5-minute window
            for host_idx, host in enumerate(visible_hosts):
                s = stats_map.get(host)
                hist = [(ts, v) for (ts, v) in s.history if ts >= window_start]
                if not hist:
                    continue
                # map times to x positions, forcing full window width usage
                points = []
                hist_start = min(t for t, _ in hist)
                hist_end = max(t for t, _ in hist)
                # Always show last 5 minutes of data at full width
                window_end = max(now_ts, hist_end)
                window_begin = min(window_start, hist_start)
                window_width = window_end - window_begin
                
                for (ts, val) in hist:
                    tfrac = (ts - window_begin) / window_width if window_width > 0 else 0
                    x = left_margin + tfrac * inner_w
                    if val is None:
                        y = top_margin + inner_h  # lost ping at bottom
                    else:
                        y = top_margin + inner_h - (float(val) / global_max) * inner_h
                    points.append((x, y))

                # flatten points for create_line
                flat = []
                for (x, y) in points:
                    flat.extend([x, y])

                col = current_colors.get(host, "#c0c0c0")
                # draw shadow and main line
                c.create_line(*flat, fill="#000000", width=3, smooth=True)
                c.create_line(*flat, fill=col, width=2, smooth=True)

            # X-axis time markers every minute
            for minute in range(6):
                t = window_start + minute * 60
                if t < window_start:
                    continue
                if t > now_ts:
                    continue
                tfrac = (t - window_start) / (now_ts - window_start)
                x = left_margin + tfrac * inner_w
                c.create_line(x, top_margin + inner_h, x, top_margin + inner_h + 6, fill="#2a2a2a")
                label = datetime.fromtimestamp(t).strftime("%H:%M")
                c.create_text(x, top_margin + inner_h + 14, text=label, anchor=tk.N, fill="#c0c0c0", font=(None, 9))
        except Exception:
            pass

    def _rebuild_legend(self, hosts: list[str], color_map: dict[str, str]) -> None:
        try:
            # Clear current legend widgets
            for child in self.legend_frame.winfo_children():
                child.destroy()
            
            # Center-aligned container for legend entries
            inner = ttk.Frame(self.legend_frame)
            inner.pack(expand=True)
            
            # Simple horizontal layout - just color boxes and host names
            for h in hosts:
                # Frame for each legend entry
                frm = ttk.Frame(inner, style="Dark.TFrame")
                frm.pack(side=tk.LEFT, padx=8)
                
                # Simple colored box
                color = color_map.get(h, "#c0c0c0")
                sw = tk.Canvas(frm, width=14, height=14, highlightthickness=0, bg="#0f0f0f")
                sw.create_rectangle(2, 2, 12, 12, fill=color, outline=color)
                sw.pack(side=tk.LEFT)
                
                # Host name - simple label with dark background
                label = ttk.Label(frm, text=h, style="Dark.TLabel")
                label.pack(side=tk.LEFT, padx=(4, 0))
        except Exception:
            pass

    def _on_legend_toggle(self, host: str, var: tk.BooleanVar) -> None:
        self._graph_visible[host] = bool(var.get())

    def _alert_blink_step(self) -> None:
        try:
            # Toggle blink state
            self._alert_blink_state = not getattr(self, "_alert_blink_state", False)
            if getattr(self, "_any_down", False):
                # Show and blink the alert bar with brighter colors
                if not self._alert_bar.winfo_ismapped():
                    self._alert_bar.pack(side=tk.TOP, fill=tk.X)
                bg = "#ff1a1a" if self._alert_blink_state else "#cc0000"
                try:
                    self._alert_bar.configure(bg=bg)
                except Exception:
                    pass
                
                # Also blink any down-state rows
                try:
                    for item in self.tree.get_children():
                        tags = list(self.tree.item(item, "tags"))
                        if "down" in tags:
                            if self._alert_blink_state:
                                if "blink" not in tags:
                                    tags.append("blink")
                            else:
                                if "blink" in tags:
                                    tags.remove("blink")
                            self.tree.item(item, tags=tags)
                except Exception:
                    pass
            else:
                if self._alert_bar.winfo_ismapped():
                    self._alert_bar.pack_forget()
                # Remove blink tag from all rows when alert cleared
                try:
                    for item in self.tree.get_children():
                        tags = list(self.tree.item(item, "tags"))
                        if "blink" in tags:
                            tags.remove("blink")
                            self.tree.item(item, tags=tags)
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            self.after(400, self._alert_blink_step)

    def _load_hosts(self) -> list[str]:
        try:
            with open(HOSTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                normalized: list[str] = []
                seen = set()
                for x in data:
                    host = self._normalize_host(str(x))
                    if host and host not in seen:
                        seen.add(host)
                        normalized.append(host)
                return normalized
            return []
        except FileNotFoundError:
            return []
        except Exception:
            return []

    def _save_hosts(self) -> None:
        hosts = sorted(self._get_all_tree_hosts())
        try:
            with open(HOSTS_FILE, "w", encoding="utf-8") as f:
                json.dump(hosts, f, indent=2)
        except Exception:
            pass

    def _on_close(self) -> None:
        try:
            # Save window geometry
            geom = self.geometry()
            self._settings["window_geometry"] = geom
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2)
        except Exception:
            pass
        finally:
            self.manager.stop_all()
            self.destroy()

    def _load_settings(self) -> dict:
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {"default_interval": DEFAULT_INTERVAL_SECONDS}

    def _normalize_host(self, raw: str) -> str:
        # Strip leading markers like '@'
        val = raw.strip()
        while val.startswith("@"):
            val = val[1:]
        # If it looks like a URL without scheme, add http:// for parsing
        tmp = val
        if "://" not in tmp:
            tmp = "http://" + tmp
        try:
            parsed = urlparse(tmp)
            host = parsed.hostname or ""
        except Exception:
            host = ""
        # Remove surrounding brackets for IPv6 if any
        if host.startswith("[") and host.endswith("]"):
            host = host[1:-1]
        return host

    def _on_about(self) -> None:
        messagebox.showinfo(APP_TITLE, "Ping multiple hosts with live status. Built with Tkinter.\n\nCredits: YvezxCode")

    def _on_export_csv(self) -> None:
        # Export current rows to a CSV in the current directory with timestamp
        import csv
        filename = f"ping_export_{int(time.time())}.csv"
        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Host", "Status", "Latency(ms)", "Avg(ms)", "Min(ms)", "Max(ms)", "Sent", "Recv", "Loss%", "Uptime%", "LastSeen", "Message"])
                for iid in self.tree.get_children(""):
                    vals = self.tree.item(iid, "values")
                    # values: icon, host, status, latency, avg, min, max, sent, received, loss, uptime, last_seen, message
                    writer.writerow([vals[1], vals[2], vals[3], vals[4], vals[5], vals[6], vals[7], vals[8], vals[9], vals[10], vals[11], vals[12]])
            messagebox.showinfo("Export", f"Saved {filename}")
        except Exception as exc:
            messagebox.showerror("Export", f"Failed to export: {exc}")

    def _toggle_column(self, col: str) -> None:
        visible = self._column_vars[col].get()
        if visible:
            self.tree.heading(col, text=self.tree.heading(col, option="text"))
            self.tree.column(col, width=90 if col in ("avg", "min", "max") else (80 if col == "uptime" else 300))
        else:
            self.tree.column(col, width=0, stretch=False)
            self.tree.heading(col, text="")

    def _on_tree_click_blank(self, event) -> None:
        # If click is not on a row, clear selection
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            self.tree.selection_remove(self.tree.selection())

    def _on_tree_double(self, event) -> None:
        # Copy host of double-clicked row to clipboard
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        host = self.tree.set(iid, "host")
        if host:
            try:
                self.clipboard_clear()
                self.clipboard_append(host)
                self._flash_status(f"Copied {host} to clipboard")
            except Exception:
                pass

    def _flash_status(self, text: str, duration_ms: int = 1500) -> None:
        # Temporary status message in the status bar
        try:
            if hasattr(self, "_status_label"):
                lbl = self._status_label
                old = lbl.cget("text")
                lbl.config(text=text)
                self.after(duration_ms, lambda: lbl.config(text=old))
        except Exception:
            pass

    def _health_pulse_step(self) -> None:
        try:
            if getattr(self, "_any_down", False):
                # pulse red to alert
                phases = ["#ff7b72", "#ff6a63", "#ff8a82", "#ff7b72"]
                color = phases[self._health_pulse_phase % len(phases)]
                self._health_canvas.itemconfig(self._health_dot, fill=color)
                self._health_pulse_phase += 1
            else:
                # steady green
                self._health_canvas.itemconfig(self._health_dot, fill="#7ee787")
                self._health_pulse_phase = 0
        except Exception:
            pass
        finally:
            self.after(300, self._health_pulse_step)

    def _on_set_interval(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Interval", "Select a host first.")
            return
        host = self.tree.set(selected[0], "host")
        current = self._settings.get("default_interval", DEFAULT_INTERVAL_SECONDS)
        try:
            value = simpledialog.askfloat("Interval", f"Set interval (seconds) for {host}", initialvalue=current, minvalue=0.2, maxvalue=60.0)
        except Exception:
            value = None
        if value is None:
            return
        self.manager.update_interval(host, value)
        self._settings["default_interval"] = float(value)


if __name__ == "__main__":
    app = PingApp()
    app.mainloop()


