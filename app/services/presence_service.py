import cv2
import time

from PySide6.QtCore import QObject, QTimer, Signal

from app.config import settings
from app.services.face_service import FaceService


class FacePresenceMonitor(QObject):
    identity_lost = Signal(object)
    error = Signal(str)

    def __init__(self, user_id, parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.camera = None
        self.face_service = None
        self.latest_frame = None
        self.last_capture_at = 0.0
        self.capture_failures = 0
        self.unavailable_reported = False
        self.capture_timer = QTimer(self)
        self.capture_timer.timeout.connect(self.capture_frame)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check)

    def start(self):
        try:
            self.unavailable_reported = False
            self.capture_failures = 0
            self.last_capture_at = 0.0
            self.face_service = FaceService()
            self.camera = cv2.VideoCapture(settings.camera_index)
            if not self.camera.isOpened():
                raise RuntimeError("ไม่สามารถเปิดกล้องสำหรับตรวจสอบผู้ใช้งานได้")
            self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.capture_frame()
            self.capture_timer.start(100)
            self.timer.start(settings.presence_scan_interval_ms)
        except Exception as error:
            self.stop()
            self.error.emit(str(error))

    def capture_frame(self):
        if self.camera is None:
            return
        success, frame = self.camera.read()
        if success:
            self.latest_frame = frame
            self.last_capture_at = time.monotonic()
            self.capture_failures = 0
        else:
            self.capture_failures += 1
            if self.capture_failures >= 20:
                self.report_camera_unavailable("กล้องหยุดส่งภาพ")

    def report_camera_unavailable(self, message):
        if self.unavailable_reported:
            return
        self.unavailable_reported = True
        self.stop()
        self.error.emit(message)

    def check(self):
        if self.camera is None or not self.camera.isOpened():
            self.report_camera_unavailable("กล้องไม่พร้อมใช้งาน")
            return
        if (
            self.latest_frame is None
            or not self.last_capture_at
            or time.monotonic() - self.last_capture_at > 3.0
        ):
            self.report_camera_unavailable("ไม่สามารถอ่านภาพจากกล้องได้")
            return
        frame = self.latest_frame.copy()
        embedding, _ = self.face_service.extract_embedding(frame)
        if embedding is None:
            self.identity_lost.emit(None)
            return
        matches, _ = self.face_service.matches_user(embedding, self.user_id)
        if not matches:
            other_user, _ = self.face_service.identify(embedding)
            self.identity_lost.emit(other_user)

    def stop(self):
        self.timer.stop()
        self.capture_timer.stop()
        self.latest_frame = None
        if self.camera is not None:
            self.camera.release()
            self.camera = None
