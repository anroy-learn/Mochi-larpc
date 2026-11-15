import math
import random
import time
from enum import Enum, auto
from typing import Optional, List, Tuple

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPainter,
    QColor,
    QBrush,
    QPen,
    QPainterPath,
    QFont,
    QRadialGradient,
    QLinearGradient,
)


class PetState(Enum):
    SIT = auto()
    LOOK_LEFT = auto()
    LOOK_RIGHT = auto()
    BLINK = auto()
    NAP = auto()
    HOP = auto()
    WALK = auto()
    POUNCE = auto()


class FloatingParticle:
    """Cute floating 'z' particle for napping or sparkle."""
    def __init__(self, x: float, y: float, text: str = "z"):
        self.x = x
        self.y = y
        self.start_y = y
        self.text = text
        self.alpha = 230
        self.life = 1.0  # 1.0 down to 0
        self.drift_speed = random.uniform(18.0, 32.0)
        self.wobble_freq = random.uniform(2.0, 4.0)
        self.start_time = time.time()

    def update(self, dt: float) -> bool:
        elapsed = time.time() - self.start_time
        self.y -= self.drift_speed * dt
        self.x += math.sin(elapsed * self.wobble_freq) * 0.4
        self.life -= dt * 0.5
        self.alpha = max(0, int(230 * self.life))
        return self.life > 0


class ProceduralPet:
    """
    Procedural renderer and animation controller for the Tab Pet.
    Features:
    - Cute squash-and-stretch physics
    - Expressive procedural eyes (blink, look, happy closed, sleeping)
    - Paws and wiggly cute ears
    - Idle behaviors: breathing, blinking, looking around, napping, random tab hops
    - Target walking and tab pouncing (for closing tabs)
    """

    def __init__(self, x: float = 100.0, y: float = 16.0):
        # Position (center bottom of the pet)
        self.x: float = x
        self.y: float = y
        self.target_x: float = x
        self.target_y: float = y

        # Base dimensions
        self.width: float = 38.0
        self.height: float = 34.0

        # Squash & stretch factors (1.0 = neutral)
        self.scale_x: float = 1.0
        self.scale_y: float = 1.0

        # Facing direction: -1 (left) or 1 (right)
        self.facing: int = 1

        # Current state & timers
        self.state: PetState = PetState.SIT
        self.state_time: float = 0.0
        self.state_duration: float = 3.0

        # Animation timing
        self.walk_speed: float = 140.0  # pixels per second
        self.hop_progress: float = 0.0  # 0.0 to 1.0 during hop
        self.hop_start_x: float = x
        self.hop_target_x: float = x
        self.hop_height: float = 18.0
        self.pounce_phase: int = 0  # 0: wind-up squash, 1: high jump, 2: stomp impact

        # Look direction offset (-1.0 to 1.0)
        self.eye_offset_x: float = 0.0
        self.eye_offset_y: float = 0.0
        self.blink_amount: float = 0.0  # 0.0 (wide open) to 1.0 (shut)

        # Floating sleep particles
        self.particles: List[FloatingParticle] = []
        self.last_particle_time: float = 0.0

        # Color palette
        self.color_body_top = QColor("#FFA07A")     # Light Salmon
        self.color_body_bottom = QColor("#FF6347")  # Tomato/warm coral
        self.color_ear_inner = QColor("#FFB6C1")    # Pastel pink
        self.color_cheeks = QColor(255, 105, 120, 150)
        self.color_eyes = QColor("#1E272C")
        self.color_belly = QColor(255, 255, 255, 170)

        # Sound toggle
        self.sound_enabled: bool = True

        # Callbacks
        self.on_reach_target = None
        self.on_pounce_complete = None

    def set_target(self, target_x: float, pounce_on_arrive: bool = False) -> None:
        """Commands the pet to walk/hop to a target tab position."""
        self.target_x = target_x
        if abs(self.target_x - self.x) > 4:
            self.facing = 1 if self.target_x > self.x else -1
            self.state = PetState.WALK
            self.state_time = 0.0
            self._pounce_on_arrive = pounce_on_arrive
        elif pounce_on_arrive:
            self.trigger_pounce()

    def trigger_pounce(self) -> None:
        """Plays the tab-closing pounce/stomp animation."""
        self.state = PetState.POUNCE
        self.state_time = 0.0
        self.pounce_phase = 0  # wind-up

    def update(self, dt: float) -> None:
        """Updates animation state, physics, and idle logic."""
        self.state_time += dt

        # Update floating particles
        self.particles = [p for p in self.particles if p.update(dt)]

        if self.state == PetState.SIT:
            self._update_sit(dt)
        elif self.state == PetState.BLINK:
            self._update_blink(dt)
        elif self.state in (PetState.LOOK_LEFT, PetState.LOOK_RIGHT):
            self._update_look(dt)
        elif self.state == PetState.NAP:
            self._update_nap(dt)
        elif self.state == PetState.WALK:
            self._update_walk(dt)
        elif self.state == PetState.HOP:
            self._update_hop(dt)
        elif self.state == PetState.POUNCE:
            self._update_pounce(dt)

    def _update_sit(self, dt: float) -> None:
        # Gentle breathing squash & stretch
        breath = math.sin(self.state_time * 3.0) * 0.05
        self.scale_x = 1.0 - breath
        self.scale_y = 1.0 + breath
        self.eye_offset_x = 0.0
        self.eye_offset_y = 0.0
        self.blink_amount = 0.0

        if self.state_time > self.state_duration:
            # Pick a new idle action
            choice = random.random()
            self.state_time = 0.0
            if choice < 0.35:
                self.state = PetState.BLINK
                self.state_duration = 0.22
            elif choice < 0.55:
                self.state = PetState.LOOK_LEFT
                self.state_duration = random.uniform(1.2, 2.2)
            elif choice < 0.75:
                self.state = PetState.LOOK_RIGHT
                self.state_duration = random.uniform(1.2, 2.2)
            elif choice < 0.90:
                self.state = PetState.NAP
                self.state_duration = random.uniform(4.0, 7.0)
            else:
                # Small spontaneous hop
                hop_dist = random.choice([-30, 30, -50, 50])
                self._start_hop(self.x + hop_dist)

    def _update_blink(self, dt: float) -> None:
        # Smooth open-close-open curve
        progress = min(1.0, self.state_time / self.state_duration)
        self.blink_amount = math.sin(progress * math.pi)
        if progress >= 1.0:
            self.blink_amount = 0.0
            self.state = PetState.SIT
            self.state_time = 0.0
            self.state_duration = random.uniform(2.0, 4.0)

    def _update_look(self, dt: float) -> None:
        target_offset = -0.7 if self.state == PetState.LOOK_LEFT else 0.7
        self.eye_offset_x += (target_offset - self.eye_offset_x) * min(1.0, dt * 10.0)
        self.eye_offset_y = 0.1
        # Gentle breathing
        breath = math.sin(self.state_time * 2.5) * 0.04
        self.scale_x = 1.0 - breath
        self.scale_y = 1.0 + breath

        if self.state_time > self.state_duration:
            self.state = PetState.SIT
            self.state_time = 0.0
            self.state_duration = random.uniform(2.0, 4.5)

    def _update_nap(self, dt: float) -> None:
        self.blink_amount = 1.0
        # Deep breathing
        deep_breath = math.sin(self.state_time * 1.5) * 0.08
        self.scale_x = 1.05 - deep_breath
        self.scale_y = 0.95 + deep_breath

        # Emit 'z' particles
        now = time.time()
        if now - self.last_particle_time > 1.2:
            self.last_particle_time = now
            spawn_x = self.x + (self.width * 0.3 * self.facing)
            spawn_y = self.y - self.height - 4
            self.particles.append(FloatingParticle(spawn_x, spawn_y, "z"))

        if self.state_time > self.state_duration:
            # Wake up stretch!
            self.state = PetState.BLINK
            self.state_time = 0.0
            self.state_duration = 0.3

    def _start_hop(self, target_x: float) -> None:
        self.state = PetState.HOP
        self.state_time = 0.0
        self.hop_start_x = self.x
        self.hop_target_x = max(30.0, target_x)
        self.facing = 1 if self.hop_target_x > self.hop_start_x else -1
        self.hop_progress = 0.0

    def _update_hop(self, dt: float) -> None:
        hop_duration = 0.38
        self.hop_progress = min(1.0, self.state_time / hop_duration)
        t = self.hop_progress

        # Horizontal lerp
        self.x = self.hop_start_x + (self.hop_target_x - self.hop_start_x) * t

        # Parabolic arc
        arc = math.sin(t * math.pi)
        self.y = self.target_y - (arc * self.hop_height)

        # Squash and stretch: stretch going up, squash landing
        if t < 0.5:
            # Ascending: stretch tall
            self.scale_x = 0.88 + 0.12 * (1.0 - t * 2)
            self.scale_y = 1.22 - 0.22 * (t * 2)
        else:
            # Descending and landing impact
            self.scale_x = 1.15
            self.scale_y = 0.85

        if t >= 1.0:
            self.x = self.hop_target_x
            self.y = self.target_y
            self.scale_x = 1.20  # landing squish
            self.scale_y = 0.80
            self.state = PetState.SIT
            self.state_time = 0.0
            self.state_duration = random.uniform(1.5, 3.5)

    def _update_walk(self, dt: float) -> None:
        dx = self.target_x - self.x
        dist = abs(dx)

        if dist < 4.0:
            self.x = self.target_x
            self.scale_x = 1.15
            self.scale_y = 0.85
            if getattr(self, "_pounce_on_arrive", False):
                self._pounce_on_arrive = False
                self.trigger_pounce()
            else:
                self.state = PetState.SIT
                self.state_time = 0.0
                self.state_duration = 2.0
                if self.on_reach_target:
                    self.on_reach_target()
            return

        # Move towards target
        step = math.copysign(min(dist, self.walk_speed * dt), dx)
        self.x += step

        # Bouncy walk rhythm
        walk_freq = 14.0
        bounce = abs(math.sin(self.state_time * walk_freq))
        self.y = self.target_y - (bounce * 8.0)
        self.scale_x = 0.92 + (0.16 * (1.0 - bounce))
        self.scale_y = 1.10 - (0.18 * (1.0 - bounce))
        self.eye_offset_x = 0.4 * self.facing

    def _update_pounce(self, dt: float) -> None:
        """
        Three phases of the tab stomp/pounce:
        0. Anticipation (crouch & squash down low) ~0.25s
        1. High leap into the air (stretch tall) ~0.30s
        2. Powerful stomp impact onto the tab! ~0.35s
        """
        if self.pounce_phase == 0:
            # Phase 0: Crouch down
            t = min(1.0, self.state_time / 0.22)
            self.scale_x = 1.0 + 0.35 * t
            self.scale_y = 1.0 - 0.40 * t
            self.y = self.target_y + (4.0 * t)
            self.eye_offset_y = 0.5
            if t >= 1.0:
                self.pounce_phase = 1
                self.state_time = 0.0

        elif self.pounce_phase == 1:
            # Phase 1: High leap
            t = min(1.0, self.state_time / 0.28)
            leap_height = 36.0
            arc = math.sin(t * math.pi)
            self.y = self.target_y - (arc * leap_height)
            self.scale_x = 0.80
            self.scale_y = 1.35
            self.eye_offset_y = -0.5
            if t >= 1.0:
                self.pounce_phase = 2
                self.state_time = 0.0

        elif self.pounce_phase == 2:
            # Phase 2: Stomp impact!
            t = min(1.0, self.state_time / 0.35)
            self.y = self.target_y
            if t < 0.4:
                # Maximum squish on landing
                self.scale_x = 1.45
                self.scale_y = 0.55
                self.blink_amount = 1.0  # happy squint
            else:
                # Elastic recovery back to neutral
                recover = (t - 0.4) / 0.6
                spring = math.sin(recover * math.pi * 3) * math.exp(-recover * 3)
                self.scale_x = 1.0 + spring * 0.25
                self.scale_y = 1.0 - spring * 0.25
                self.blink_amount = 0.0

            if t >= 1.0:
                self.scale_x = 1.0
                self.scale_y = 1.0
                self.state = PetState.SIT
                self.state_time = 0.0
                self.state_duration = 2.5
                if self.sound_enabled:
                    try:
                        from PySide6.QtWidgets import QApplication
                        QApplication.beep()
                    except Exception:
                        pass
                if self.on_pounce_complete:
                    self.on_pounce_complete()

    def draw(self, painter: QPainter) -> None:
        """Procedurally draws the pet and its particles using QPainter."""
        # 1. Draw floating particles (sleep 'z's, etc.)
        if self.particles:
            painter.save()
            font = QFont("Helvetica", 11, QFont.Weight.Bold)
            painter.setFont(font)
            for p in self.particles:
                painter.setPen(QColor(135, 206, 250, p.alpha))
                painter.drawText(QPointF(p.x, p.y), p.text)
            painter.restore()

        # 2. Draw Pet with current transform (centered at self.x, grounded at self.y)
        painter.save()
        painter.translate(self.x, self.y)
        painter.scale(self.scale_x * self.facing, self.scale_y)

        # Enable high-quality anti-aliasing
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pw = self.width
        ph = self.height

        # Cute soft drop shadow
        painter.setPen(Qt.PenStyle.NoPen)
        shadow_rect = QRectF(-pw * 0.42, -3.0, pw * 0.84, 6.0)
        painter.setBrush(QColor(0, 0, 0, 35))
        painter.drawEllipse(shadow_rect)

        # Body Gradient
        body_grad = QLinearGradient(0, -ph, 0, 0)
        body_grad.setColorAt(0.0, self.color_body_top)
        body_grad.setColorAt(1.0, self.color_body_bottom)

        # Ears (wiggly cute cat/bear ears)
        ear_pen = QPen(self.color_body_bottom, 1.2)
        painter.setPen(ear_pen)
        painter.setBrush(body_grad)

        # Left Ear
        left_ear = QPainterPath()
        left_ear.moveTo(-pw * 0.38, -ph * 0.75)
        left_ear.lineTo(-pw * 0.32, -ph * 1.08)
        left_ear.lineTo(-pw * 0.12, -ph * 0.88)
        left_ear.closeSubpath()
        painter.drawPath(left_ear)

        # Right Ear
        right_ear = QPainterPath()
        right_ear.moveTo(pw * 0.12, -ph * 0.88)
        right_ear.lineTo(pw * 0.32, -ph * 1.08)
        right_ear.lineTo(pw * 0.38, -ph * 0.75)
        right_ear.closeSubpath()
        painter.drawPath(right_ear)

        # Inner ear pink accents
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.color_ear_inner)
        left_inner = QPainterPath()
        left_inner.moveTo(-pw * 0.34, -ph * 0.78)
        left_inner.lineTo(-pw * 0.30, -ph * 1.0)
        left_inner.lineTo(-pw * 0.16, -ph * 0.86)
        left_inner.closeSubpath()
        painter.drawPath(left_inner)

        right_inner = QPainterPath()
        right_inner.moveTo(pw * 0.16, -ph * 0.86)
        right_inner.lineTo(pw * 0.30, -ph * 1.0)
        right_inner.lineTo(pw * 0.34, -ph * 0.78)
        right_inner.closeSubpath()
        painter.drawPath(right_inner)

        # Main Body (cute rounded pear/squircle)
        body_rect = QRectF(-pw / 2.0, -ph, pw, ph)
        painter.setPen(QPen(QColor(230, 80, 50, 160), 1.2))
        painter.setBrush(body_grad)
        painter.drawRoundedRect(body_rect, pw * 0.44, ph * 0.48)

        # Soft light belly patch
        belly_rect = QRectF(-pw * 0.28, -ph * 0.50, pw * 0.56, ph * 0.44)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.color_belly)
        painter.drawEllipse(belly_rect)

        # Cheek Blushes
        painter.setBrush(self.color_cheeks)
        painter.drawEllipse(QRectF(-pw * 0.42, -ph * 0.44, 7.0, 4.5))
        painter.drawEllipse(QRectF(pw * 0.42 - 7.0, -ph * 0.44, 7.0, 4.5))

        # Eyes & Mouth
        self._draw_face(painter, pw, ph)

        # Cute front little paws resting on the bottom
        painter.setBrush(self.color_body_top)
        painter.setPen(QPen(QColor(230, 80, 50, 140), 1.0))
        painter.drawRoundedRect(QRectF(-pw * 0.32, -3.5, 7.5, 5.0), 3.0, 3.0)
        painter.drawRoundedRect(QRectF(pw * 0.32 - 7.5, -3.5, 7.5, 5.0), 3.0, 3.0)

        painter.restore()

    def _draw_face(self, painter: QPainter, pw: float, ph: float) -> None:
        eye_y = -ph * 0.55
        eye_spacing = pw * 0.24
        eye_size = 5.2

        look_dx = self.eye_offset_x * 2.2
        look_dy = self.eye_offset_y * 1.5

        if self.blink_amount > 0.65:
            # Closed happy arc eyes ^ ^
            pen = QPen(self.color_eyes, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            # Left eye arc
            l_path = QPainterPath()
            l_path.moveTo(-eye_spacing - 3.2, eye_y + 1.0)
            l_path.quadTo(-eye_spacing, eye_y - 2.8, -eye_spacing + 3.2, eye_y + 1.0)
            painter.drawPath(l_path)

            # Right eye arc
            r_path = QPainterPath()
            r_path.moveTo(eye_spacing - 3.2, eye_y + 1.0)
            r_path.quadTo(eye_spacing, eye_y - 2.8, eye_spacing + 3.2, eye_y + 1.0)
            painter.drawPath(r_path)
        else:
            # Open eyes with pupil and highlight gleams
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.color_eyes)

            # Left eye
            l_rect = QRectF(
                -eye_spacing - (eye_size / 2.0) + look_dx,
                eye_y - (eye_size / 2.0) + look_dy,
                eye_size,
                eye_size * (1.0 - self.blink_amount * 0.8),
            )
            painter.drawEllipse(l_rect)

            # Right eye
            r_rect = QRectF(
                eye_spacing - (eye_size / 2.0) + look_dx,
                eye_y - (eye_size / 2.0) + look_dy,
                eye_size,
                eye_size * (1.0 - self.blink_amount * 0.8),
            )
            painter.drawEllipse(r_rect)

            # White catchlight sparkles
            painter.setBrush(Qt.GlobalColor.white)
            sparkle_r = 1.4
            painter.drawEllipse(QRectF(l_rect.x() + 1.2, l_rect.y() + 1.0, sparkle_r * 2, sparkle_r * 2))
            painter.drawEllipse(QRectF(r_rect.x() + 1.2, r_rect.y() + 1.0, sparkle_r * 2, sparkle_r * 2))

        # Cute tiny mouth :3
        pen_mouth = QPen(QColor(80, 50, 40, 180), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_mouth)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        mouth_path = QPainterPath()
        mouth_y = eye_y + 4.8
        mouth_path.moveTo(-2.2, mouth_y)
        mouth_path.quadTo(-1.1, mouth_y + 1.6, 0.0, mouth_y + 0.4)
        mouth_path.quadTo(1.1, mouth_y + 1.6, 2.2, mouth_y)
        painter.drawPath(mouth_path)
