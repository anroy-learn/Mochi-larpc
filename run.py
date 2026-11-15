import sys
import signal
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from overlay.config import ConfigManager
from overlay.window import PetOverlayWindow


def main():
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Enable high DPI scaling
    app = QApplication(sys.argv)
    app.setApplicationName("TabPet")

    config = ConfigManager()
    print("=" * 60)
    print("🐾 Tab Pet Overlay started!")
    print(f"🔑 Auth Token: {config.get('auth_token')}")
    print(f"⚙️ Config location: {config.get('tab_offset_x')}px X-offset, {config.get('tab_offset_y')}px Y-offset")
    print("=" * 60)

    window = PetOverlayWindow(config)
    window.show()

    # Step 1 interactive demo: every 6 seconds, simulate hopping to a different tab index
    # to demonstrate dynamic positioning, squash-and-stretch, and smooth hopping!
    demo_tab_index = 0
    total_demo_tabs = 5

    def demo_hop():
        nonlocal demo_tab_index
        demo_tab_index = (demo_tab_index + 1) % total_demo_tabs
        window.move_pet_to_tab(demo_tab_index, tab_count=total_demo_tabs, pounce=False)

    demo_timer = QTimer()
    demo_timer.timeout.connect(demo_hop)
    demo_timer.start(7000)

    # Timer to allow Python signal handling (Ctrl+C) to process
    sig_timer = QTimer()
    sig_timer.start(500)
    sig_timer.timeout.connect(lambda: None)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
