import sys
import time
import ctypes
import ctypes.util
from collections import deque
from typing import Optional, Tuple, Deque

from PySide6.QtCore import Qt, QTimer, QPoint, QRect, Slot
from PySide6.QtGui import QPainter, QGuiApplication, QColor
from PySide6.QtWidgets import QWidget

from overlay.pet import ProceduralPet, PetState
from overlay.config import ConfigManager
from overlay.server import ServerBridge, TabPetServer


def configure_macos_window(win_id: int) -> None:
    """
    Configures macOS Cocoa native window flags:
    - setHidesOnDeactivate:NO (prevents Cocoa from hiding the overlay when Chrome is active)
    - setCollectionBehavior (makes pet visible across all Spaces and Fullscreen apps)
    - setLevel (ensures pet floats permanently above Chrome)
    - setIgnoresMouseEvents:YES (ensures all mouse clicks pass straight to Chrome tabs)
    """
    if sys.platform != "darwin":
        return

    try:
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]

        sel_window = objc.sel_registerName(b"window")
        sel_set_hides = objc.sel_registerName(b"setHidesOnDeactivate:")
        sel_set_collection = objc.sel_registerName(b"setCollectionBehavior:")
        sel_set_level = objc.sel_registerName(b"setLevel:")
        sel_set_ignores = objc.sel_registerName(b"setIgnoresMouseEvents:")

        # Send [view window] to get the NSWindow
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        objc.objc_msgSend.restype = ctypes.c_void_p
        ns_window = objc.objc_msgSend(win_id, sel_window)

        if not ns_window:
            ns_window = win_id

        # 1. Do NOT hide when deactivating
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
        objc.objc_msgSend.restype = None
        objc.objc_msgSend(ns_window, sel_set_hides, False)

        # 2. CanJoinAllSpaces (1) | FullScreenAuxiliary (256)
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        objc.objc_msgSend.restype = None
        objc.objc_msgSend(ns_window, sel_set_collection, 1 | 256)

        # 3. Status Window Level (25) - stays on top of Chrome at all times
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
        objc.objc_msgSend.restype = None
        objc.objc_msgSend(ns_window, sel_set_level, 25)

        # 4. Pass mouse clicks through to Chrome tabs beneath the pet
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
        objc.objc_msgSend.restype = None
        objc.objc_msgSend(ns_window, sel_set_ignores, True)

    except Exception as e:
        print(f"[Overlay] Native macOS window setup warning: {e}")


class BlockedTask:
    def __init__(self, tab_id: int, tab_index: int, tab_count: int, url: str):
        self.tab_id = tab_id
        self.tab_index = tab_index
        self.tab_count = tab_count
        self.url = url


class PetOverlayWindow(QWidget):
    """
    Transparent, click-through, always-on-top overlay window that sits
    directly over the Chrome tab bar.
    """

    STRIP_HEIGHT = 70  # Height of the overlay strip above the tab line

    def __init__(
        self,
        config_manager: ConfigManager,
        bridge: Optional[ServerBridge] = None,
        server: Optional[TabPetServer] = None
    ):
        super().__init__()
        self.config = config_manager
        self.bridge = bridge
        self.server = server

        # Overlay geometry state
        self.chrome_bounds: Optional[Tuple[int, int, int, int]] = None
        self.tab_count: int = 1
        self.active_tab_index: int = 0

        # Blocked tabs queue
        self.blocked_queue: Deque[BlockedTask] = deque()
        self.current_blocked_task: Optional[BlockedTask] = None

        # Setup pet and position
        tab_y_offset = float(self.config.get("tab_offset_y", 14))
        self.pet_ground_y = float(self.STRIP_HEIGHT - tab_y_offset)
        self.pet = ProceduralPet(x=120.0, y=self.pet_ground_y)
        self.pet.sound_enabled = bool(self.config.get("sound_enabled", True))

        self._init_window()
        self._init_timers()
        self._connect_signals()

    def _init_window(self) -> None:
        """Sets window flags for transparent, always-on-top overlay."""
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setWindowFlags(flags)

        # Translucent background
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setStyleSheet("background: transparent;")

        # Default size and position across top screen
        screen = QGuiApplication.primaryScreen()
        if screen:
            screen_geo = screen.geometry()
            default_w = min(1512, screen_geo.width())
            default_x = 0
            default_y = 30  # Sits right on Chrome tab bar below menu bar
            self.setGeometry(default_x, default_y, default_w, self.STRIP_HEIGHT)
        else:
            self.setGeometry(0, 30, 1200, self.STRIP_HEIGHT)

        self.setWindowTitle("TabPetOverlay")

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Apply macOS Cocoa native window configuration
        configure_macos_window(int(self.winId()))

    def _init_timers(self) -> None:
        """60 FPS render and animation update loop."""
        self.last_update_time = time.time()
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._on_tick)
        self.anim_timer.start(16)  # ~60 fps

    def _connect_signals(self) -> None:
        if not self.bridge:
            return

        self.bridge.bounds_received.connect(self.on_bounds_received)
        self.bridge.tab_activated.connect(self.on_tab_activated)
        self.bridge.blocked_tab_opened.connect(self.on_blocked_tab_opened)
        self.bridge.calibration_updated.connect(self.on_calibration_updated)

    def _on_tick(self) -> None:
        now = time.time()
        dt = min(0.05, now - self.last_update_time)
        self.last_update_time = now

        # Update pet physics and animations
        self.pet.update(dt)

        # Repaint canvas
        self.update()

    # -------------------------------------------------------------
    # Slots & Signal Handlers
    # -------------------------------------------------------------
    @Slot(int, int, int, int, int)
    def on_bounds_received(self, left: int, top: int, width: int, height: int, tab_count: int) -> None:
        """Follows Chrome window bounds live."""
        # Sanity check: prevent moving offscreen if Chrome sends minimized coordinates
        if left < -2000 or top < -2000 or width < 200:
            return

        # On macOS, Chrome's tab strip sits right below the menu bar (y ≈ 28-33)
        if top >= 80:
            top = 30
        else:
            top = max(0, top)

        self.chrome_bounds = (left, top, width, height)
        self.tab_count = max(1, tab_count)

        self.setGeometry(left, top, max(300, width), self.STRIP_HEIGHT)
        self.move_pet_to_tab(self.active_tab_index, self.tab_count, pounce=False)

    @Slot(int, int)
    def on_tab_activated(self, tab_index: int, tab_count: int) -> None:
        """Hops to the active tab index if not currently busy closing a blocked tab."""
        if self.current_blocked_task or len(self.blocked_queue) > 0:
            return

        self.move_pet_to_tab(tab_index, tab_count=tab_count, pounce=False)

    @Slot(int, int, int, str, str)
    def on_blocked_tab_opened(self, tab_id: int, tab_index: int, tab_count: int, url: str, title: str) -> None:
        """Queues a blocked tab to be closed."""
        print(f"[Overlay] 🚨 Blocked tab detected: id={tab_id}, index={tab_index}, url={url}")
        task = BlockedTask(tab_id, tab_index, tab_count, url)
        self.blocked_queue.append(task)

        if not self.current_blocked_task:
            self._process_next_blocked_tab()

    def _process_next_blocked_tab(self) -> None:
        if not self.blocked_queue:
            self.current_blocked_task = None
            return

        task = self.blocked_queue.popleft()
        self.current_blocked_task = task

        target_x = self.config.calculate_tab_x(self.width(), task.tab_index, task.tab_count)
        target_x = max(25.0, min(float(self.width() - 35), target_x))

        self.pet.set_target(target_x, pounce_on_arrive=True)

        def on_pounce_finished():
            print(f"[Overlay] 💥 Pounce complete for tab {task.tab_id}! Requesting close.")
            if self.server:
                self.server.notify_tab_closed(task.tab_id)

            QTimer.singleShot(250, self._process_next_blocked_tab)

        self.pet.on_pounce_complete = on_pounce_finished

    @Slot()
    def on_calibration_updated(self) -> None:
        """Updates pet ground level, sound settings, and active position when calibration changes."""
        tab_y_offset = float(self.config.get("tab_offset_y", 14))
        self.pet_ground_y = float(self.STRIP_HEIGHT - tab_y_offset)
        self.pet.y = self.pet_ground_y
        self.pet.target_y = self.pet_ground_y
        self.pet.sound_enabled = bool(self.config.get("sound_enabled", True))

    def move_pet_to_tab(self, tab_index: int, tab_count: Optional[int] = None, pounce: bool = False) -> None:
        """Commands pet to navigate to a specific tab index."""
        if tab_count is not None:
            self.tab_count = max(1, tab_count)
        self.active_tab_index = tab_index

        window_width = self.width()
        target_x = self.config.calculate_tab_x(window_width, tab_index, self.tab_count)
        target_x = max(25.0, min(float(window_width - 35), target_x))

        self.pet.set_target(target_x, pounce_on_arrive=pounce)

    def paintEvent(self, event) -> None:
        """Paints the procedural pet over the transparent canvas."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.pet.draw(painter)
        painter.end()
