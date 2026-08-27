import sys

from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
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

    # The login window must not appear until VachanaTTS is fully loaded.
    try:
        ThaiTTSService.prepare()
    except Exception as error:
        QMessageBox.critical(
            None,
            "TTS Error",
            f"ไม่สามารถเตรียมระบบเสียง VachanaTTS ได้\n{error}",
        )
        return

    window = MainWindow()

    window.show()

    sys.exit(
        application.exec()
    )
