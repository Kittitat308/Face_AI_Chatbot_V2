from dataclasses import dataclass
from enum import Enum, auto

import cv2
from PySide6.QtCore import (
    QMetaObject,
    QObject,
    QThread,
    QTimer,
    Qt,
    Signal,
    Slot,
)

from app.config import settings
from app.services.face_service import FaceScanResult, FaceService


NORMAL_SCAN_INTERVAL = 60000
WARNING_SCAN_INTERVAL = 1000
SWITCH_VERIFY_INTERVAL = 1000
MAX_MISSED_SCANS = 5
LOGOUT_COUNTDOWN_SECONDS = 5
SWITCH_CONFIRM_COUNT = 2


class MonitorState(Enum):
    ACTIVE = auto()
    VERIFY_SWITCH = auto()
    LOGOUT_WARNING = auto()


class MonitorAction(Enum):
    CONTINUE = auto()
    NO_FACE = auto()
    SHOW_WARNING = auto()
    VERIFY_SWITCH = auto()
    SWITCH_USER = auto()
    LOGOUT_IMMEDIATELY = auto()


@dataclass(frozen=True)
class MonitorDecision:
    action: MonitorAction
    user: object | None = None


class SessionMonitorState:
    """Pure state machine implementing post-login face decision priority."""

    def __init__(self, current_user_id):
        self.current_user_id = current_user_id
        self.miss_count = 0
        self.switch_candidate = None
        self.switch_confirm_count = 0
        self.countdown_seconds = LOGOUT_COUNTDOWN_SECONDS
        self.monitor_state = MonitorState.ACTIVE

    def cancel_switch_verification(self):
        self.switch_candidate = None
        self.switch_confirm_count = 0

    def reset_missing_state(self):
        self.miss_count = 0
        self.countdown_seconds = LOGOUT_COUNTDOWN_SECONDS

    def reset_all(self, current_user_id=None):
        if current_user_id is not None:
            self.current_user_id = current_user_id
        self.reset_missing_state()
        self.cancel_switch_verification()
        self.monitor_state = MonitorState.ACTIVE

    def handle_missing_face(self):
        """Count a scan where the current user is absent or unrecognized."""
        self.cancel_switch_verification()
        self.miss_count += 1
        if self.miss_count >= MAX_MISSED_SCANS:
            self.monitor_state = MonitorState.LOGOUT_WARNING
            return MonitorDecision(MonitorAction.SHOW_WARNING)
        self.monitor_state = MonitorState.ACTIVE
        return MonitorDecision(MonitorAction.NO_FACE)

    def process(self, result: FaceScanResult):
        if result.current_user_found:
            self.reset_all()
            return MonitorDecision(MonitorAction.CONTINUE)

        if result.face_count >= 2:
            self.cancel_switch_verification()
            if result.unknown_face_found:
                return self.handle_missing_face()
            return MonitorDecision(MonitorAction.LOGOUT_IMMEDIATELY)

        if result.face_count == 1:
            recognized = result.recognized_user
            if recognized is None:
                return self.handle_missing_face()

            if recognized.id == self.current_user_id:
                self.reset_all()
                return MonitorDecision(MonitorAction.CONTINUE)

            if (
                self.switch_candidate is not None
                and self.switch_candidate.id == recognized.id
            ):
                self.switch_confirm_count += 1
            else:
                self.switch_candidate = recognized
                self.switch_confirm_count = 1

            self.monitor_state = MonitorState.VERIFY_SWITCH
            if self.switch_confirm_count >= SWITCH_CONFIRM_COUNT:
                user = self.switch_candidate
                self.reset_all(current_user_id=user.id)
                return MonitorDecision(MonitorAction.SWITCH_USER, user)
            return MonitorDecision(MonitorAction.VERIFY_SWITCH, recognized)

        return self.handle_missing_face()


class FaceMonitorWorker(QObject):
    scan_result = Signal(object)
    error = Signal(str)
    finished = Signal()

    def __init__(
        self,
        current_user_id,
        interval,
        face_service=None,
        camera=None,
    ):
        super().__init__()
        self.current_user_id = current_user_id
        self.interval = interval
        self.camera = camera
        # Reuse the already-prepared login service when available so entering
        # Chatbot does not load the InsightFace models for a second time.
        self.face_service = face_service
        self.scan_timer = None
        self.stopping = False

    @Slot()
    def start(self):
        try:
            # Face Login normally hands us its already-open VideoCapture.
            # Opening a new device is only a fallback for manual login or when
            # the login camera was unavailable/disabled.
            if self.camera is None:
                self.camera = cv2.VideoCapture(settings.camera_index)
            if not self.camera.isOpened():
                raise RuntimeError("ไม่สามารถเปิดกล้องสำหรับตรวจสอบผู้ใช้งานได้")
            self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if self.face_service is None:
                self.face_service = FaceService()
            if QThread.currentThread().isInterruptionRequested():
                self.stop()
                return
            self.scan_timer = QTimer(self)
            self.scan_timer.timeout.connect(self.perform_scan)
            self.scan_timer.start(self.interval)
        except Exception as error:
            self.error.emit(str(error))
            self.stop()

    @Slot()
    def perform_scan(self):
        if self.stopping or QThread.currentThread().isInterruptionRequested():
            return
        if self.camera is None or not self.camera.isOpened():
            self.error.emit("กล้องไม่พร้อมใช้งาน")
            self.stop()
            return
        success, frame = self.camera.read()
        if not success:
            self.error.emit("ไม่สามารถอ่านภาพจากกล้องได้")
            self.stop()
            return
        try:
            result = self.face_service.analyze_session_frame(
                frame, self.current_user_id
            )
            if not self.stopping:
                self.scan_result.emit(result)
        except Exception as error:
            self.error.emit(str(error))
            self.stop()

    @Slot(int)
    def set_interval(self, interval):
        self.interval = interval
        if self.scan_timer is not None and self.scan_timer.isActive():
            self.scan_timer.start(interval)

    @Slot(int)
    def set_current_user(self, user_id):
        self.current_user_id = user_id

    @Slot()
    def stop(self):
        if self.stopping:
            return
        self.stopping = True
        if self.scan_timer is not None:
            self.scan_timer.stop()
        if self.camera is not None:
            self.camera.release()
            self.camera = None
        self.finished.emit()


class FacePresenceMonitor(QObject):
    scan_result = Signal(object)
    error = Signal(str)
    interval_requested = Signal(int)
    user_requested = Signal(int)

    def __init__(self, user_id, parent=None, face_service=None, camera=None):
        super().__init__(parent)
        self.user_id = user_id
        self.face_service = face_service
        self.camera = camera
        self.thread = None
        self.worker = None

    def start(self):
        if self.thread is not None:
            return
        self.thread = QThread(self)
        self.worker = FaceMonitorWorker(
            self.user_id,
            NORMAL_SCAN_INTERVAL,
            self.face_service,
            self.camera,
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.start)
        self.worker.scan_result.connect(self.scan_result)
        self.worker.error.connect(self.error)
        self.worker.finished.connect(self.thread.quit)
        self.interval_requested.connect(self.worker.set_interval)
        self.user_requested.connect(self.worker.set_current_user)
        self.thread.start()

    def set_interval(self, interval):
        if self.worker is not None:
            self.interval_requested.emit(interval)

    def set_current_user(self, user_id):
        self.user_id = user_id
        if self.worker is not None:
            self.user_requested.emit(user_id)

    def stop(self):
        thread = self.thread
        worker = self.worker
        if thread is None:
            return
        thread.requestInterruption()
        if thread.isRunning() and worker is not None:
            try:
                QMetaObject.invokeMethod(
                    worker,
                    "stop",
                    Qt.BlockingQueuedConnection,
                )
            except RuntimeError:
                pass
            thread.quit()
            thread.wait()
        self.worker = None
        self.thread = None
        thread.deleteLater()
