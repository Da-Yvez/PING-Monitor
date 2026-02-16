import os
import platform
import queue
import re
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Optional, Deque, Tuple


LATENCY_REGEXES = [
    re.compile(r"time[=<]\s*([0-9]+\.?[0-9]*)\s*ms", re.IGNORECASE),  # time=12.3 ms or time<1 ms
    re.compile(r"=\s*([0-9]+\.?[0-9]*)ms", re.IGNORECASE),  # =12ms (fallback)
]

# Number of history points to keep per-host (used for sparkline graph)
HISTORY_MAX = 3000


@dataclass
class HostStats:
    host: str
    sent: int = 0
    received: int = 0
    last_latency_ms: Optional[float] = None
    last_status: str = "Unknown"  # Up/Down/Unknown
    last_message: str = ""
    last_seen_epoch: Optional[float] = None
    first_seen_epoch: Optional[float] = None
    latency_min_ms: Optional[float] = None
    latency_max_ms: Optional[float] = None
    latency_sum_ms: float = 0.0
    latency_count: int = 0
    # recent latency values as (timestamp, value) where value is None for loss
    # stored oldest->newest with maxlen HISTORY_MAX
    history: Deque[Tuple[float, Optional[float]]] = field(default_factory=lambda: deque(maxlen=HISTORY_MAX))

    def loss_percent(self) -> float:
        if self.sent == 0:
            return 0.0
        lost = self.sent - self.received
        return (lost / self.sent) * 100.0

    def avg_latency_ms(self) -> Optional[float]:
        if self.latency_count == 0:
            return None
        return self.latency_sum_ms / self.latency_count

    def uptime_percent(self) -> float:
        if self.sent == 0:
            return 0.0
        return (self.received / self.sent) * 100.0


class PingWorker(threading.Thread):
    def __init__(self, host: str, update_queue: "queue.Queue[HostStats]", stop_event: threading.Event, interval_seconds: float = 1.0):
        super().__init__(daemon=True)
        self.host = host
        self.update_queue = update_queue
        self.stop_event = stop_event
        self.interval_seconds = max(0.2, interval_seconds)
        self.stats = HostStats(host=host)

    def run(self) -> None:
        while not self.stop_event.is_set():
            self.stats.sent += 1
            success, latency_ms, message = self._ping_once(self.host)
            if success:
                self.stats.received += 1
                self.stats.last_status = "Up"
                self.stats.last_latency_ms = latency_ms
                self.stats.last_seen_epoch = time.time()
                if self.stats.first_seen_epoch is None:
                    self.stats.first_seen_epoch = self.stats.last_seen_epoch
                if latency_ms is not None:
                    self.stats.latency_sum_ms += latency_ms
                    self.stats.latency_count += 1
                    if self.stats.latency_min_ms is None or latency_ms < self.stats.latency_min_ms:
                        self.stats.latency_min_ms = latency_ms
                    if self.stats.latency_max_ms is None or latency_ms > self.stats.latency_max_ms:
                        self.stats.latency_max_ms = latency_ms
            else:
                self.stats.last_status = "Down"
                self.stats.last_latency_ms = None
            # Append history entry (None for failed pings)
            try:
                try:
                    self.stats.history.append((time.time(), latency_ms if success else None))
                except Exception:
                    pass
            except Exception:
                # history should always exist, but ignore if not
                pass
            self.stats.last_message = message

            try:
                self.update_queue.put_nowait(self.stats)
            except queue.Full:
                # Drop updates if UI is behind; next one will catch up
                pass

            self.stop_event.wait(self.interval_seconds)

    @staticmethod
    def _ping_once(host: str) -> tuple[bool, Optional[float], str]:
        system = platform.system().lower()
        commands: list[list[str]] = []
        if system == "windows":
            # -n 1: one packet, -w 1000: 1s timeout
            commands.append(["ping", "-n", "1", "-w", "1000", host])
            commands.append(["ping", "-4", "-n", "1", "-w", "1000", host])
            commands.append(["ping", "-6", "-n", "1", "-w", "1000", host])
        else:
            # -c 1: one packet, -W 1: 1s timeout, -n: numeric
            commands.append(["ping", "-n", "-c", "1", "-W", "1", host])
            commands.append(["ping", "-4", "-n", "-c", "1", "-W", "1", host])
            commands.append(["ping", "-6", "-n", "-c", "1", "-W", "1", host])

        last_output = ""
        for cmd in commands:
            try:
                # Common kwargs for subprocess.run
                run_kwargs = dict(capture_output=True, text=True, timeout=4)

                # On Windows, prevent a new console window from being created for each ping child process.
                # This avoids the brief console flash when running a GUI executable created with PyInstaller.
                if system == "windows":
                    try:
                        # Preferred approach: creationflags (available on Windows)
                        run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                    except Exception:
                        # Fallback: use STARTUPINFO to hide window
                        si = subprocess.STARTUPINFO()
                        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        si.wShowWindow = subprocess.SW_HIDE
                        run_kwargs["startupinfo"] = si

                completed = subprocess.run(cmd, **run_kwargs)
                stdout = completed.stdout or ""
                stderr = completed.stderr or ""
                output = stdout + ("\n" + stderr if stderr else "")
                last_output = output
                ok = completed.returncode == 0

                latency_ms = None
                for regex in LATENCY_REGEXES:
                    m = regex.search(output)
                    if m:
                        try:
                            latency_ms = float(m.group(1))
                        except ValueError:
                            latency_ms = None
                        break

                if ok:
                    return True, latency_ms, output.strip().splitlines()[-1] if output else ""
            except Exception:
                # try next variant
                pass

        return False, None, last_output.strip().splitlines()[-1] if last_output else ""


class PingManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._update_queue: "queue.Queue[HostStats]" = queue.Queue(maxsize=1000)
        self._workers: Dict[str, PingWorker] = {}
        self._stops: Dict[str, threading.Event] = {}

    @property
    def update_queue(self) -> "queue.Queue[HostStats]":
        return self._update_queue

    def add_host(self, host: str, interval_seconds: float = 1.0) -> None:
        host = host.strip()
        if not host:
            return
        with self._lock:
            if host in self._workers:
                return
            stop_event = threading.Event()
            worker = PingWorker(host, self._update_queue, stop_event, interval_seconds=interval_seconds)
            self._workers[host] = worker
            self._stops[host] = stop_event
            worker.start()

    def remove_host(self, host: str) -> None:
        with self._lock:
            stop = self._stops.pop(host, None)
            worker = self._workers.pop(host, None)
        if stop is not None:
            stop.set()
        if worker is not None:
            worker.join(timeout=2)

    def list_hosts(self) -> list[str]:
        with self._lock:
            return list(self._workers.keys())

    def stats_snapshot(self) -> Dict[str, HostStats]:
        """Return a shallow copy of current HostStats objects (safe for UI reading)."""
        with self._lock:
            # return copies to avoid UI touching internal objects directly
            out: Dict[str, HostStats] = {}
            for h, w in self._workers.items():
                try:
                    # create a shallow dataclass copy
                    s = w.stats
                    copy_stats = HostStats(
                        host=s.host,
                        sent=s.sent,
                        received=s.received,
                        last_latency_ms=s.last_latency_ms,
                        last_status=s.last_status,
                        last_message=s.last_message,
                        last_seen_epoch=s.last_seen_epoch,
                        first_seen_epoch=s.first_seen_epoch,
                        latency_min_ms=s.latency_min_ms,
                        latency_max_ms=s.latency_max_ms,
                        latency_sum_ms=s.latency_sum_ms,
                        latency_count=s.latency_count,
                        # Return the history deque directly, as it's already a copy with maxlen
                        history=s.history,
                    )
                    out[h] = copy_stats
                except Exception:
                    pass
            return out

    def update_interval(self, host: str, interval_seconds: float) -> None:
        interval_seconds = max(0.2, float(interval_seconds))
        with self._lock:
            worker = self._workers.get(host)
        if worker is not None:
            worker.interval_seconds = interval_seconds

    def stop_all(self) -> None:
        with self._lock:
            stops = list(self._stops.values())
            workers = list(self._workers.values())
            self._stops.clear()
            self._workers.clear()
        for s in stops:
            s.set()
        for w in workers:
            w.join(timeout=2)


