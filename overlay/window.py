import sys
import time
from collections import deque
from typing import Optional, Tuple, Deque

from PySide6.QtCore import Qt, QTimer, QPoint, Slot
from PySide6.QtGui import QPainter, QMouseEvent
from PySide6.QtWidgets import QWidget

from overlay.pet import ProceduralPet, PetState
from overlay.config import ConfigManager
from overlay.server import ServerBridge, TabPetServer


class BlockedTask:
    def __init__(self, tab_id: int, tab_index: int, tab_count: int, url: str):
        self.tab_id = tab_id
        self.tab_index = tab_index
        self.tab_count = tab_count
        self.url = url


class PetOverlayWindow(QWidget):
    """
    Compact, floating Desktop Pet (76x76 px).
    Features:
    - Physically lives on the active Chrome tab as an independent desktop character.
    - Moves smoothly across the screen along the tab bar when switching tabs or closing blocked tabs.
    - NEVER covers the rest of the tab bar (only 76px wide right where it sits).
    - Fully draggable with the mouse anywhere on screen.
    - Petting interaction: clicking the pet squashes it happily and emits hearts.
    """

    PET_SIZE = 76  # Compact window dimension

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

        # Chrome window reference
        self.chrome_left: int = 0
        self.chrome_top: int = 22
        self.chrome_width: int = 1512
        self.tab_count: int = 1
        self.active_tab_index: int = 0

        # Physical screen position & walking kinematics
        self.screen_x: float = 200.0
        self.screen_y: float = float(self.chrome_top)
        self.target_screen_x: float = 200.0
        self.target_screen_y: float = float(self.chrome_top)
        self.walk_speed: float = 480.0  # Pixels per second

        # Dragging state
        self.is_dragging: bool = False
        self.drag_offset = QPoint()

        # Blocked tabs queue
        self.blocked_queue: Deque[BlockedTask] = deque()
        self.current_blocked_task: Optional[BlockedTask] = None

        # Procedural pet renderer (centered in the 76x76 canvas)
        # Ground at y = 62
        self.pet = ProceduralPet(x=self.PET_SIZE / 2.0, y=62.0)
        self.pet.sound_enabled = bool(self.config.get("sound_enabled", True))

        self._init_window()
        self._init_timers()
        self._connect_signals()

    def _init_window(self) -> None:
        """Sets window flags for floating, transparent compact pet."""
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowFlags(flags)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setFixedSize(self.PET_SIZE, self.PET_SIZE)

        # Place initial position above first tab
        initial_x = self.config.calculate_tab_x(self.chrome_width, 0, 1) - (self.PET_SIZE / 2.0)
        self.screen_x = max(10.0, initial_x)
        self.target_screen_x = self.screen_x
        self.move(int(self.screen_x), int(self.screen_y))

        self.setWindowTitle("TabPet")

    def _init_timers(self) -> None:
        """60 FPS render and kinematic movement loop."""
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

        # Update walking movement across screen towards target tab
        if not self.is_dragging:
            dx = self.target_screen_x - self.screen_x
            dist = abs(dx)

            if dist > 3.0:
                # Walk across tab bar towards target
                direction = 1 if dx > 0 else -1
                step = min(dist, self.walk_speed * dt)
                self.screen_x += direction * step
                self.pet.facing = direction
                self.pet.state = PetState.WALK
                self.move(int(self.screen_x), int(self.screen_y))
            else:
                self.screen_x = self.target_screen_x
                self.move(int(self.screen_x), int(self.screen_y))

                # Check if we arrived at a blocked tab
                if self.current_blocked_task and self.pet.state == PetState.WALK:
                    self.pet.trigger_pounce()
                elif self.pet.state == PetState.WALK:
                    self.pet.state = PetState.SIT
                    self.pet.state_time = 0.0

        # Update pet physics and procedural animations
        self.pet.update(dt)

        # Repaint canvas
        self.update()

    # -------------------------------------------------------------
    # Mouse Interactions: Petting and Dragging
    # -------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.pet.pet_touch()
            self.is_dragging = True
            self.drag_offset = event.globalPosition().toPoint() - self.pos()
            self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.is_dragging:
            new_pos = event.globalPosition().toPoint() - self.drag_offset
            self.move(new_pos)
            self.screen_x = float(new_pos.x())
            self.screen_y = float(new_pos.y())
            self.target_screen_x = self.screen_x
            self.target_screen_y = self.screen_y
            self.pet.start_drag()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.is_dragging:
            self.is_dragging = False
            self.pet.end_drag(62.0)
            self.update()
        super().mouseReleaseEvent(event)

    # -------------------------------------------------------------
    # Signal Handlers & Live Chrome Sync
    # -------------------------------------------------------------
    @Slot(int, int, int, int, int)
    def on_bounds_received(self, left: int, top: int, width: int, height: int, tab_count: int) -> None:
        """Updated Chrome window position and dimensions."""
        self.chrome_left = max(0, left)
        # Tab bar is directly under the menu bar on macOS (y ≈ 20-25)
        self.chrome_top = 22
        self.chrome_width = max(300, width)
        self.tab_count = max(1, tab_count)
        self.screen_y = float(self.chrome_top)
        self.target_screen_y = self.screen_y

        if not self.is_dragging:
            self.move_pet_to_tab(self.active_tab_index, self.tab_count, pounce=False)

    @Slot(int, int)
    def on_tab_activated(self, tab_index: int, tab_count: int) -> None:
        """Active tab changed: pet walks over to new tab."""
        if self.is_dragging or self.current_blocked_task or len(self.blocked_queue) > 0:
            return
        self.move_pet_to_tab(tab_index, tab_count=tab_count, pounce=False)

    @Slot(int, int, int, str, str)
    def on_blocked_tab_opened(self, tab_id: int, tab_index: int, tab_count: int, url: str, title: str) -> None:
        """Queue blocked tab: pet marches over to stomp it shut."""
        print(f"[DesktopPet] 🚨 Blocked tab detected: id={tab_id}, index={tab_index}, url={url}")
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

        # Set target to blocked tab's horizontal position
        tab_center_x = self.config.calculate_tab_x(self.chrome_width, task.tab_index, task.tab_count)
        self.target_screen_x = self.chrome_left + tab_center_x - (self.PET_SIZE / 2.0)

        def on_pounce_finished():
            print(f"[DesktopPet] 💥 Stomped tab {task.tab_id}! Closing now.")
            if self.server:
                self.server.notify_tab_closed(task.tab_id)
            QTimer.singleShot(300, self._process_next_blocked_tab)

        self.pet.on_pounce_complete = on_pounce_finished

    @Slot()
    def on_calibration_updated(self) -> None:
        """Live calibration change."""
        self.pet.sound_enabled = bool(self.config.get("sound_enabled", True))
        if not self.is_dragging:
            self.move_pet_to_tab(self.active_tab_index, self.tab_count, pounce=False)

    def move_pet_to_tab(self, tab_index: int, tab_count: Optional[int] = None, pounce: bool = False) -> None:
        """Sets the target tab for the pet to walk to."""
        if tab_count is not None:
            self.tab_count = max(1, tab_count)
        self.active_tab_index = tab_index

        tab_center_x = self.config.calculate_tab_x(self.chrome_width, tab_index, self.tab_count)
        self.target_screen_x = self.chrome_left + tab_center_x - (self.PET_SIZE / 2.0)

    def paintEvent(self, event) -> None:
        """Paints the procedural pet inside its 76x76 transparent canvas."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.pet.draw(painter)
        painter.end()
