from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QPushButton,
    QGroupBox,
    QCheckBox,
)

from overlay.config import ConfigManager


class CalibrationDialog(QWidget):
    """
    Visual calibration window with sliders to calibrate:
    - Tab bar X offset (left padding)
    - Tab bar Y offset (vertical alignment)
    - Max tab width
    """

    def __init__(self, config_manager: ConfigManager, on_change_callback=None):
        super().__init__()
        self.config = config_manager
        self.on_change_callback = on_change_callback

        self.setWindowTitle("🐾 Tab Pet Calibration")
        self.setFixedSize(360, 310)
        # Normal window, not click-through so user can interact with sliders
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("Tab Position Calibration")
        form_layout = QVBoxLayout(group)

        # 1. Tab Offset X Slider
        current_x = self.config.get("tab_offset_x", 80)
        self.label_x = QLabel(f"Left Offset (X): {current_x} px")
        self.slider_x = QSlider(Qt.Orientation.Horizontal)
        self.slider_x.setRange(20, 200)
        self.slider_x.setValue(current_x)
        self.slider_x.valueChanged.connect(self._on_x_changed)
        form_layout.addWidget(self.label_x)
        form_layout.addWidget(self.slider_x)

        # 2. Tab Offset Y Slider
        current_y = self.config.get("tab_offset_y", 14)
        self.label_y = QLabel(f"Vertical Offset (Y): {current_y} px")
        self.slider_y = QSlider(Qt.Orientation.Horizontal)
        self.slider_y.setRange(0, 45)
        self.slider_y.setValue(current_y)
        self.slider_y.valueChanged.connect(self._on_y_changed)
        form_layout.addWidget(self.label_y)
        form_layout.addWidget(self.slider_y)

        # 3. Max Tab Width Slider
        current_max_w = self.config.get("max_tab_width", 240)
        self.label_w = QLabel(f"Max Tab Width: {current_max_w} px")
        self.slider_w = QSlider(Qt.Orientation.Horizontal)
        self.slider_w.setRange(120, 320)
        self.slider_w.setValue(current_max_w)
        self.slider_w.valueChanged.connect(self._on_w_changed)
        form_layout.addWidget(self.label_w)
        form_layout.addWidget(self.slider_w)

        # 4. Sound Effects Checkbox
        self.sound_check = QCheckBox("Enable Sound Effects")
        self.sound_check.setChecked(bool(self.config.get("sound_enabled", True)))
        self.sound_check.toggled.connect(self._on_sound_toggled)
        form_layout.addWidget(self.sound_check)

        layout.addWidget(group)

        # Reset button
        btn_layout = QHBoxLayout()
        reset_btn = QPushButton("Reset Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(reset_btn)

        close_btn = QPushButton("Save & Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _on_x_changed(self, value: int) -> None:
        self.label_x.setText(f"Left Offset (X): {value} px")
        self.config.set("tab_offset_x", value)
        if self.on_change_callback:
            self.on_change_callback()

    def _on_y_changed(self, value: int) -> None:
        self.label_y.setText(f"Vertical Offset (Y): {value} px")
        self.config.set("tab_offset_y", value)
        if self.on_change_callback:
            self.on_change_callback()

    def _on_w_changed(self, value: int) -> None:
        self.label_w.setText(f"Max Tab Width: {value} px")
        self.config.set("max_tab_width", value)
        if self.on_change_callback:
            self.on_change_callback()

    def _on_sound_toggled(self, checked: bool) -> None:
        self.config.set("sound_enabled", checked)
        if self.on_change_callback:
            self.on_change_callback()

    def _reset_defaults(self) -> None:
        self.slider_x.setValue(80)
        self.slider_y.setValue(14)
        self.slider_w.setValue(240)
