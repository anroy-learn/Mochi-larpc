import sys
import signal
import argparse
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from overlay.config import ConfigManager
from overlay.memory import MemoryStore
from overlay.ai import GeminiPetAI
from overlay.server import ServerBridge, TabPetServer
from overlay.window import PetOverlayWindow
from overlay.calibration import CalibrationDialog
from overlay.tracker import NativeChromeTracker


def main():
    parser = argparse.ArgumentParser(description="Tab Pet - Desktop Chrome Tab Guardian")
    parser.add_argument("--calibrate", action="store_true", help="Open calibration sliders window")
    parser.add_argument("--demo", action="store_true", help="Run in self-demo mode without extension")
    args = parser.parse_args()

    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    app.setApplicationName("TabPet")

    config = ConfigManager()
    token = config.get("auth_token")
    port = config.get("port", 8765)

    print("=" * 65)
    print("🐾 Tab Pet Overlay & Guardian Server")
    print(f"🔑 Auth Token: {token}")
    print(f"🌐 WebSocket URL: ws://127.0.0.1:{port}/ws?token={token}")
    print(f"📏 Calibrated offsets: X={config.get('tab_offset_x')}px, Y={config.get('tab_offset_y')}px, MaxTabW={config.get('max_tab_width')}px")
    print("=" * 65)

    # Memory Store and AI Controller
    memory = MemoryStore()
    ai = GeminiPetAI(memory)

    # Qt Signal Bridge
    bridge = ServerBridge()

    # Native macOS Chrome tracker (auto-tracks Chrome even before extension connects)
    tracker = NativeChromeTracker(bridge)
    tracker.start()

    # FastAPI + WebSocket Server
    server = TabPetServer(config, bridge, ai=ai, memory=memory)
    server.start_background()

    # Overlay Window
    window = PetOverlayWindow(config, bridge=bridge, server=server, ai=ai, memory=memory)
    window.show()
    window.raise_()
    window.activateWindow()

    calibration_dialog = None
    if args.calibrate:
        def on_calib_change():
            bridge.calibration_updated.emit()
        calibration_dialog = CalibrationDialog(config, on_change_callback=on_calib_change)
        calibration_dialog.show()

    if args.demo:
        print("[Demo] Self-demo mode active: pet will hop across simulated tabs.")
        demo_tab_index = 0
        total_demo_tabs = 5

        def demo_hop():
            nonlocal demo_tab_index
            demo_tab_index = (demo_tab_index + 1) % total_demo_tabs
            window.move_pet_to_tab(demo_tab_index, tab_count=total_demo_tabs, pounce=(demo_tab_index == 3))

        demo_timer = QTimer()
        demo_timer.timeout.connect(demo_hop)
        demo_timer.start(5000)

    # Periodic timer to allow Python signal handling (Ctrl+C) to process
    sig_timer = QTimer()
    sig_timer.start(500)
    sig_timer.timeout.connect(lambda: None)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
