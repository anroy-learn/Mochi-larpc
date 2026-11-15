import sys
import time
import ctypes
import ctypes.util
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QTimer, QPoint, QRect
from PySide6.QtGui import QPainter, QGuiApplication, QColor
from PySide6.QtWidgets import QWidget

from overlay.pet import ProceduralPet, PetState
from overlay.config import ConfigManager


def make_macos_click_through(win_id: int) -> None:
    """
    Directly invokes Cocoa's [NSWindow setIgnoresMouseEvents:YES] on macOS.
    This guarantees that all mouse events (clicks, scrolls, drags) pass directly
    through the overlay window to Chrome tabs and buttons beneath it.
    """
    if sys.platform != "darwin":
        return

    try:
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]

        sel_window = objc.sel_registerName(b"window")
        sel_set_ignores = objc.sel_registerName(b"setIgnoresMouseEvents:")

        # Send [view window] to get the NSWindow
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        objc.objc_msgSend.restype = ctypes.c_void_p
        ns_window = objc.objc_msgSend(win_id, sel_window)

        if not ns_window:
            ns_window = win_id

        # Send [nsWindow setIgnoresMouseEvents:YES]
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
        objc.objc_msgSend.restype = None
        objc.objc_msgSend(ns_window, sel_set_ignores, True)
    except Exception as e:
        print(f"[Overlay] Native click-through warning: {e}")


class PetOverlayWindow(QWidget):
    """
    Transparent, click-through, always-on-top overlay window that sits
    directly over the Chrome tab bar.
    """

    STRIP_HEIGHT = 70  # Height of the overlay strip above the tab line

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config = config_manager

        # Overlay geometry state
        self.chrome_bounds: Optional[Tuple[int, int, int, int]] = None
        self.tab_count: int = 1
        self.active_tab_index: int = 0

        # Setup pet and position
        tab_y_offset = float(self.config.get("tab_offset_y", 14))
        # The pet rests at y = STRIP_HEIGHT - tab_y_offset
        self.pet_ground_y = float(self.STRIP_HEIGHT - tab_y_offset)
        self.pet = ProceduralPet(x=120.0, y=self.pet_ground_y)

        self._init_window()
        self._init_timers()

    def _init_window(self) -> None:
        """Sets window flags for transparent, always-on-top, click-through overlay."""
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.Tool  # Doesn't appear as separate icon in macOS Dock
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
            default_w = min(1280, screen_geo.width() - 80)
            default_x = (screen_geo.width() - default_w) // 2
            default_y = 25  # Just below macOS menu bar
            self.setGeometry(default_x, default_y, default_w, self.STRIP_HEIGHT)
        else:
            self.setGeometry(100, 30, 1000, self.STRIP_HEIGHT)

        self.setWindowTitle("TabPetOverlay")

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Apply macOS Cocoa native mouse pass-through
        make_macos_click_through(int(self.winId()))

    def _init_timers(self) -> None:
        """60 FPS render and animation update loop."""
        self.last_update_time = time.time()
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._on_tick)
        self.anim_timer.start(16)  # ~60 fps

    def _on_tick(self) -> None:
        now = time.time()
        dt = min(0.05, now - self.last_update_time)
        self.last_update_time = now

        # Update pet physics and animations
        self.pet.update(dt)

        # Request repaint
        self.update()

    def update_chrome_bounds(self, left: int, top: int, width: int, height: int, tab_count: int = 1) -> None:
        """
        Called when the Chrome extension sends updated window bounds.
        Reposition overlay window directly over Chrome's tab strip.
        """
        self.chrome_bounds = (left, top, width, height)
        self.tab_count = max(1, tab_count)

        # Position overlay at the top strip of the Chrome window
        # Chrome tab bar sits at the top of the Chrome window.
        # macOS titlebar / tabstrip is at window top (y = 0 to 45px).
        strip_y = top
        self.setGeometry(left, strip_y, max(200, width), self.STRIP_HEIGHT)

    def move_pet_to_tab(self, tab_index: int, tab_count: Optional[int] = None, pounce: bool = False) -> None:
        """Commands pet to navigate to a specific tab index."""
        if tab_count is not None:
            self.tab_count = max(1, tab_count)
        self.active_tab_index = tab_index

        window_width = self.width()
        target_x = self.config.calculate_tab_x(window_width, tab_index, self.tab_count)

        # Constrain inside window
        target_x = max(25.0, min(float(window_width - 35), target_x))
        self.pet.set_target(target_x, pounce_on_arrive=pounce)

    def trigger_close_animation(self, on_complete=None) -> None:
        """Triggers pounce / stomp animation when tab is closed."""
        self.pet.on_pounce_complete = on_complete
        self.pet.trigger_pounce()

    def paintEvent(self, event) -> None:
        """Paints the procedural pet over the transparent canvas."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.pet.draw(painter)
        painter.end()
