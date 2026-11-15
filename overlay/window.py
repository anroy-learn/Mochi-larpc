import sys
import time
import asyncio
import threading
from collections import deque
from typing import Optional, Tuple, Deque

from PySide6.QtCore import Qt, QTimer, QPoint, Slot, QRect
from PySide6.QtGui import QPainter, QMouseEvent, QRegion
from PySide6.QtWidgets import QWidget

from overlay.pet import ProceduralPet, PetState
from overlay.config import ConfigManager
from overlay.server import ServerBridge, TabPetServer
from overlay.ai import GeminiPetAI
from overlay.memory import MemoryStore


class BlockedTask:
    def __init__(
        self,
        tab_id: int,
        tab_index: int,
        tab_count: int,
        url: str,
        title: str = "",
        blocks_today: int = 1,
        streak_days: int = 1,
        goal: str = ""
    ):
        self.tab_id = tab_id
        self.tab_index = tab_index
        self.tab_count = tab_count
        self.url = url
        self.title = title
        self.blocks_today = blocks_today
        self.streak_days = streak_days
        self.goal = goal
        self.roast_text = ""
        self.roast_offline = False

        # Extract clean domain for prompt
        clean = url.split("?")[0].split("#")[0]
        if "//" in clean:
            self.domain = clean.split("/")[2]
        else:
            self.domain = clean


class PetOverlayWindow(QWidget):
    """
    Compact, floating Desktop Pet (76x76 px).
    Features:
    - Physically lives on the active Chrome tab as an independent desktop character.
    - Moves smoothly across the screen along the tab bar when switching tabs or closing blocked tabs.
    - Expands dynamically only when displaying roast speech bubbles.
    - Fully draggable with the mouse anywhere on screen.
    - Petting interaction: clicking the pet squashes it happily and emits hearts.
    - Mood expressions synchronized with user Trust Score.
    """

    PET_SIZE = 76  # Compact window dimension
    BUBBLE_WIDTH = 210
    BUBBLE_HEIGHT = 130

    def __init__(
        self,
        config_manager: ConfigManager,
        bridge: Optional[ServerBridge] = None,
        server: Optional[TabPetServer] = None,
        ai: Optional[GeminiPetAI] = None,
        memory: Optional[MemoryStore] = None
    ):
        super().__init__()
        self.config = config_manager
        self.bridge = bridge
        self.server = server
        self.ai = ai
        self.memory = memory

        # Chrome window reference
        self.chrome_left: int = 0
        self.chrome_top: int = int(self.config.get("tab_offset_y", 18))
        self.chrome_width: int = 1512
        self.tab_count: int = 1
        self.active_tab_index: int = 0

        # Physical screen position & walking kinematics
        self.screen_x: float = 200.0
        self.screen_y: float = float(self.chrome_top)
        self.target_screen_x: float = 200.0
        self.target_screen_y: float = float(self.chrome_top)
        self.walk_speed: float = 480.0  # Pixels per second

        # Speech bubble expansion state
        self.is_bubble_active: bool = False
        self.bubble_shrink_timer: Optional[QTimer] = None

        # Dragging state
        self.is_dragging: bool = False
        self.drag_offset = QPoint()

        # Blocked tabs queue
        self.blocked_queue: Deque[BlockedTask] = deque()
        self.current_blocked_task: Optional[BlockedTask] = None

        # Procedural pet renderer (centered in the 76x76 canvas)
        self.pet = ProceduralPet(x=self.PET_SIZE / 2.0, y=62.0)
        self.pet.sound_enabled = bool(self.config.get("sound_enabled", True))
        if self.memory:
            self.pet.mood = self.memory.get_notes_summary().get("mood", "neutral")

        self._init_window()
        self._init_timers()
        self._connect_signals()

    def _init_window(self) -> None:
        """Sets window flags for floating, transparent compact pet."""
        flags = (
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
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
        self.bridge.trust_updated.connect(self.on_trust_updated)

    def _on_tick(self) -> None:
        now = time.time()
        dt = min(0.05, now - self.last_update_time)
        self.last_update_time = now

        # Update walking movement across screen towards target tab
        if not self.is_dragging:
            dx = self.target_screen_x - self.screen_x
            dist = abs(dx)

            if dist > 3.0:
                direction = 1 if dx > 0 else -1
                step = min(dist, self.walk_speed * dt)
                self.screen_x += direction * step
                self.pet.facing = direction
                self.pet.state = PetState.WALK
                self._apply_window_position()
            else:
                self.screen_x = self.target_screen_x
                self._apply_window_position()

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

    def _apply_window_position(self) -> None:
        if self.is_bubble_active:
            # Shift window up and centered so pet remains on tab strip while speech bubble expands above
            draw_x = self.screen_x - ((self.BUBBLE_WIDTH - self.PET_SIZE) / 2.0)
            draw_y = self.screen_y - (self.BUBBLE_HEIGHT - self.PET_SIZE)
            self.move(int(draw_x), int(draw_y))
        else:
            self.move(int(self.screen_x), int(self.screen_y))

    # -------------------------------------------------------------
    # Roast Speech Bubble Expansion
    # -------------------------------------------------------------
    def show_roast_bubble(self, roast_text: str, is_offline: bool = False, duration: float = 4.0) -> None:
        self.is_bubble_active = True
        self.setFixedSize(self.BUBBLE_WIDTH, self.BUBBLE_HEIGHT)
        self.pet.x = self.BUBBLE_WIDTH / 2.0
        self.pet.y = 116.0
        self.pet.target_x = self.pet.x
        self.pet.target_y = self.pet.y
        self.pet.show_speech(roast_text, is_offline=is_offline, duration=duration)
        self._apply_window_position()

        # Mask so transparent areas outside pet and bubble pass through clicks to Chrome
        bx = int(self.pet.x - 98.0)
        by = int(self.pet.y - 34.0 - 54.0 - 14.0)
        bubble_rect = QRect(max(0, bx - 2), max(0, by - 2), 200, 60)
        tail_rect = QRect(int(self.pet.x - 12), by + 54, 24, 12)
        pet_rect = QRect(int(self.pet.x - 32), int(self.pet.y - 42), 64, 52)
        mask = QRegion(bubble_rect).united(QRegion(tail_rect)).united(QRegion(pet_rect))
        self.setMask(mask)

        if self.bubble_shrink_timer:
            self.bubble_shrink_timer.stop()

        self.bubble_shrink_timer = QTimer(self)
        self.bubble_shrink_timer.setSingleShot(True)
        self.bubble_shrink_timer.timeout.connect(self._shrink_bubble)
        self.bubble_shrink_timer.start(int((duration + 0.1) * 1000))

    def _shrink_bubble(self) -> None:
        self.is_bubble_active = False
        self.clearMask()
        self.setFixedSize(self.PET_SIZE, self.PET_SIZE)
        self.pet.x = self.PET_SIZE / 2.0
        self.pet.y = 62.0
        self.pet.target_x = self.pet.x
        self.pet.target_y = self.pet.y
        self._apply_window_position()

    # -------------------------------------------------------------
    # Mouse Interactions: Petting and Dragging
    # -------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if self.is_bubble_active:
            # If user clicked on or near the speech bubble, dismiss it immediately
            bx = int(self.pet.x - 98.0)
            by = int(self.pet.y - 34.0 - 54.0 - 14.0)
            bubble_area = QRect(bx - 2, by - 2, 200, 68)
            if bubble_area.contains(pos):
                self._shrink_bubble()
                return

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
        self.chrome_top = int(self.config.get("tab_offset_y", 18))
        self.chrome_width = max(300, width)
        self.tab_count = max(1, tab_count)
        self.screen_y = float(self.chrome_top)
        self.target_screen_y = self.screen_y

        if not self.is_dragging and not self.current_blocked_task:
            self.move_pet_to_tab(self.active_tab_index, self.tab_count, pounce=False)

    @Slot(int, int)
    def on_tab_activated(self, tab_index: int, tab_count: int) -> None:
        """Active tab changed: pet walks over to new tab."""
        if self.is_dragging or self.current_blocked_task or len(self.blocked_queue) > 0:
            return
        self.move_pet_to_tab(tab_index, tab_count=tab_count, pounce=False)

    @Slot(int, str)
    def on_trust_updated(self, trust_score: int, mood: str) -> None:
        """Updates pet mood expression when trust changes."""
        self.pet.mood = mood

    @Slot(int, int, int, str, str, int, int, str)
    def on_blocked_tab_opened(
        self,
        tab_id: int,
        tab_index: int,
        tab_count: int,
        url: str,
        title: str,
        blocks_today: int,
        streak_days: int,
        goal: str
    ) -> None:
        """Queue blocked tab: pet marches over to stomp it shut and deliver roast."""
        print(f"[DesktopPet] 🚨 Blocked tab: id={tab_id}, index={tab_index}, url={url}, goal='{goal}'")
        task = BlockedTask(
            tab_id=tab_id,
            tab_index=tab_index,
            tab_count=tab_count,
            url=url,
            title=title,
            blocks_today=blocks_today,
            streak_days=streak_days,
            goal=goal
        )

        # Generate roast in background while pet walks
        if self.ai:
            def _async_roast():
                try:
                    loop = asyncio.new_event_loop()
                    roast, is_offline = loop.run_until_complete(
                        self.ai.generate_roast(
                            tab_title=title,
                            tab_domain=task.domain,
                            blocks_today=blocks_today,
                            streak_days=streak_days,
                            goal=goal
                        )
                    )
                    loop.close()
                    task.roast_text = roast
                    task.roast_offline = is_offline
                except Exception as e:
                    print(f"[DesktopPet] Roast generation error: {e}")
                    task.roast_offline = True
            threading.Thread(target=_async_roast, daemon=True).start()

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
            roast = task.roast_text
            is_offline = task.roast_offline
            if not roast:
                roast = "Distraction stomped! Back to work."
                is_offline = True
            print(f"[DesktopPet] 💥 Stomped tab {task.tab_id}! Roast: '{roast}' (offline={is_offline})")
            
            # Show speech bubble above pet for ~4 seconds
            self.show_roast_bubble(roast, is_offline=is_offline, duration=4.0)

            if self.server:
                self.server.notify_tab_closed(task.tab_id, roast)

            QTimer.singleShot(4200, self._process_next_blocked_tab)

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
        """Paints the procedural pet inside its transparent canvas."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.pet.draw(painter)
        painter.end()
