import sys

from PySide6.QtWidgets import (
    QApplication,
)

from app.config import (
    settings,
)

from app.database import (
    init_database,
)

from app.ui.main_window import (
    MainWindow,
)
from app.services.tts_service import ThaiTTSService


def main():

    init_database()

    application = QApplication(
        sys.argv
    )

    application.setApplicationName(
        settings.app_name
    )

    # Preload TTS when possible, but missing audio support must not prevent
    # account login or text chat (important for headless Raspberry Pi setups).
    try:
        ThaiTTSService.prepare()
    except Exception:
        pass

    window = MainWindow()

    window.show()

    sys.exit(
        application.exec()
    )
