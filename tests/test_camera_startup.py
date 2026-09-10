import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QCoreApplication

from app.services.presence_service import FaceMonitorWorker
from app.ui.main_window import MainWindow


class CameraStartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QCoreApplication.instance() or QCoreApplication([])

    def test_chat_camera_starts_before_ui_history_and_tts(self):
        order = []
        face_service = object()
        window = SimpleNamespace(
            login_widget=SimpleNamespace(face_service=face_service),
            face_service=None,
            welcome_audio_ready=True,
            current_user=None,
            session_monitor_state=None,
            start_presence_monitor=lambda: order.append("camera"),
            build_chat_interface=lambda: order.append("ui"),
            load_chats=lambda: order.append("history"),
            prepare_welcome_in_background=lambda user: order.append("tts"),
        )
        user = SimpleNamespace(
            id=1,
            display_name="A",
            camera_enabled=True,
            speaker_enabled=True,
        )

        with patch("app.ui.main_window.FaceService.update_cached_user"):
            MainWindow.on_login(window, user)

        self.assertIs(window.face_service, face_service)
        self.assertEqual(order, ["camera", "ui", "history", "tts"])

    def test_monitor_reuses_handed_off_camera_without_reopening_device(self):
        camera = MagicMock()
        camera.isOpened.return_value = True
        worker = FaceMonitorWorker(
            current_user_id=1,
            interval=60000,
            face_service=object(),
            camera=camera,
        )

        with patch("app.services.presence_service.cv2.VideoCapture") as open_camera:
            worker.start()
            open_camera.assert_not_called()

        worker.stop()
        camera.release.assert_called_once()


if __name__ == "__main__":
    unittest.main()
