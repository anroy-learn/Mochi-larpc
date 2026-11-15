import sys
import time
import subprocess
import threading
from typing import Optional, Tuple

from overlay.server import ServerBridge


class NativeChromeTracker:
    """
    Native macOS Chrome window and tab tracker.
    Automatically queries Chrome's front window bounds and active tab index
    via AppleScript so the pet immediately tracks Chrome even before or without
    the Chrome extension being installed!
    """

    APPLESCRIPT_QUERY = (
        'tell application "Google Chrome" to get '
        '{bounds of front window, active tab index of front window, count of tabs of front window}'
    )

    def __init__(self, bridge: ServerBridge, interval_sec: float = 0.25):
        self.bridge = bridge
        self.interval = interval_sec
        self.running = False
        self._thread: Optional[threading.Thread] = None

        # Track previous state to avoid redundant signal emissions
        self.last_bounds: Optional[Tuple[int, int, int, int]] = None
        self.last_tab_index: Optional[int] = None
        self.last_tab_count: Optional[int] = None

    def start(self) -> None:
        if sys.platform != "darwin" or self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="ChromeTrackerThread")
        self._thread.start()
        print("[Tracker] Native macOS Chrome tracker started.")

    def stop(self) -> None:
        self.running = False

    def _poll_loop(self) -> None:
        while self.running:
            try:
                self._query_chrome()
            except Exception:
                pass
            time.sleep(self.interval)

    def _query_chrome(self) -> None:
        # Check if Chrome is front window or running
        res = subprocess.run(
            ["osascript", "-e", self.APPLESCRIPT_QUERY],
            capture_output=True,
            text=True,
            timeout=1.5,
        )
        if res.returncode != 0:
            return

        raw = res.stdout.strip()
        if not raw:
            return

        parts = [p.strip() for p in raw.split(",")]
        if len(parts) < 6:
            return

        x1 = int(parts[0])
        y1 = int(parts[1])
        x2 = int(parts[2])
        y2 = int(parts[3])
        active_tab_1based = int(parts[4])
        tab_count = int(parts[5])

        left = x1
        top = y1
        width = x2 - x1
        height = y2 - y1
        tab_index = max(0, active_tab_1based - 1)  # 0-indexed

        # Ignore invalid / minimized bounds
        if width < 200 or height < 100 or left < -2000 or top < -2000:
            return

        # On macOS, Chrome's tab strip is at the top of the Chrome window (y=28-33 below menu bar).
        # AppleScript sometimes returns the webview content origin (y=121). Clamp tab strip to top of window:
        if top >= 80:
            top = 30

        # Check for window bounds change
        current_bounds = (left, top, width, height)
        if current_bounds != self.last_bounds or tab_count != self.last_tab_count:
            self.last_bounds = current_bounds
            self.last_tab_count = tab_count
            self.bridge.bounds_received.emit(left, top, width, height, tab_count)

        # Check for tab change
        if tab_index != self.last_tab_index:
            self.last_tab_index = tab_index
            self.bridge.tab_activated.emit(tab_index, tab_count)
