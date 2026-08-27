import cv2

from PySide6.QtCore import (
    Qt,
    QTimer,
    Signal,
)

from PySide6.QtGui import (
    QImage,
    QPixmap,
)

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QMessageBox,
)

from app.config import settings

from app.services.face_service import (
    FaceService,
)

from app.ui.create_user import (
    CreateUserDialog,
)
from app.ui.auth_dialog import ManualLoginDialog, PasswordDialog


class FaceLoginWidget(QWidget):

    logged_in = Signal(object)

    camera_error = Signal(str)


    def __init__(self):

        super().__init__()

        self.face_service = None

        self.camera = None
        self.last_frame = None
        self.dialog_open = False
        self.camera_available = False

        self.preview = QLabel(
            "กำลังเตรียมระบบ Face Recognition..."
        )

        self.preview.setAlignment(
            Qt.AlignCenter
        )

        self.preview.setMinimumSize(
            700,
            520,
        )

        self.status = QLabel(
            "มองกล้องเพื่อเข้าสู่ระบบ"
        )

        self.status.setAlignment(
            Qt.AlignCenter
        )

        self.create_button = QPushButton(
            "สร้างผู้ใช้ใหม่"
        )

        self.create_button.clicked.connect(
            self.open_create_user
        )

        self.manual_login_button = QPushButton(
            "เข้าสู่ระบบด้วยบัญชีหรืออีเมล"
        )
        self.manual_login_button.clicked.connect(self.open_manual_login)

        layout = QVBoxLayout(
            self
        )

        layout.addWidget(
            self.preview
        )

        layout.addWidget(
            self.status
        )

        layout.addWidget(
            self.create_button
        )

        layout.addWidget(self.manual_login_button)

        self.timer = QTimer(
            self
        )

        self.timer.timeout.connect(
            self.process_frame
        )
        self.preview_timer = QTimer(self)
        self.preview_timer.timeout.connect(self.update_preview)


    def start(self):

        try:

            if self.face_service is None:
                self.face_service = FaceService()

            self.camera = (
                cv2.VideoCapture(
                    settings.camera_index
                )
            )

            if not self.camera.isOpened():

                raise RuntimeError(
                    "ไม่สามารถเปิดกล้องได้"
                )

            self.camera_available = True
            self.preview_timer.start(80)
            self.timer.start(settings.login_scan_interval_ms)

        except Exception as error:
            self.stop()
            self.camera_error.emit(
                str(error)
            )


    def process_frame(self):
        if self.camera is None or self.last_frame is None or self.dialog_open:
            return
        frame = self.last_frame.copy()

        embedding, face = (
            self.face_service
            .extract_embedding(
                frame
            )
        )

        frame = (
            self.face_service
            .draw_face_box(
                frame,
                face,
            )
        )

        if embedding is not None:

            user, score = (
                self.face_service
                .identify(
                    embedding
                )
            )

            if user is not None:
                self.status.setText(f"พบคุณ{user.display_name} ({score:.2f})")
                if user.require_password_after_face:
                    self.open_password_dialog(user)
                else:
                    self.stop()
                    self.logged_in.emit(user)
                return

            self.status.setText(
                "ไม่พบผู้ใช้ กำลังเปิดหน้าสร้างบัญชี..."
            )
            self.open_create_user()

        else:

            self.status.setText(self.face_service.last_error or "กรุณาให้ใบหน้าอยู่ในกล้อง")


    def update_preview(self):
        if self.camera is None:
            return
        success, frame = self.camera.read()
        if not success:
            return
        self.last_frame = cv2.flip(frame, 1)
        self.show_frame(self.last_frame)


    def open_password_dialog(self, user):
        self.dialog_open = True
        self.stop()
        dialog = PasswordDialog(user, self)
        if dialog.exec() and dialog.authenticated_user is not None:
            self.logged_in.emit(dialog.authenticated_user)
            return
        self.dialog_open = False
        self.start()


    def open_manual_login(self):
        if self.dialog_open:
            return
        camera_was_available = self.camera_available
        self.dialog_open = True
        self.stop()
        dialog = ManualLoginDialog(self)
        if dialog.exec() and dialog.authenticated_user is not None:
            self.logged_in.emit(dialog.authenticated_user)
            return
        self.dialog_open = False
        if camera_was_available:
            self.start()


    def show_frame(
        self,
        frame,
    ):

        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB,
        )

        height, width, channels = (
            rgb.shape
        )

        image = QImage(
            rgb.data,
            width,
            height,
            channels * width,
            QImage.Format_RGB888,
        )

        self.preview.setPixmap(
            QPixmap.fromImage(
                image
            ).scaled(
                self.preview.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )


    def open_create_user(self):

        if self.face_service is None:

            QMessageBox.warning(
                self,
                "Face Recognition",
                "ระบบ Face Recognition "
                "ยังไม่พร้อม",
            )

            return

        if self.dialog_open:
            return
        self.dialog_open = True
        self.stop()
        try:
            dialog = CreateUserDialog(self.face_service)
        except Exception as error:
            self.dialog_open = False
            QMessageBox.critical(self, "Camera", str(error))
            self.start()
            return

        if dialog.exec():
            self.logged_in.emit(
                dialog.created_user
            )
            return
        self.dialog_open = False
        self.start()


    def stop(self):

        self.timer.stop()
        self.preview_timer.stop()

        if self.camera:

            self.camera.release()

            self.camera = None
        self.camera_available = False


    def closeEvent(
        self,
        event,
    ):

        self.stop()

        event.accept()
