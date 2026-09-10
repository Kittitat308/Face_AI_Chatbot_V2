import cv2

from PySide6.QtCore import (
    QTimer,
    Qt,
)

from PySide6.QtGui import (
    QImage,
    QPixmap,
)

from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QFormLayout,
    QMessageBox,
)

from app.repositories import (
    create_user,
    add_face_embedding,
    validate_username,
)
from app.config import settings
from app.services.password_service import validate_password


class CreateUserDialog(QDialog):

    def __init__(
        self,
        face_service,
    ):

        super().__init__()

        self.setWindowTitle(
            "Create User"
        )

        self.resize(
            700,
            650,
        )

        self.face_service = face_service
        self.camera_handoff = None

        self.camera = cv2.VideoCapture(settings.camera_index)
        if not self.camera.isOpened():
            raise RuntimeError("ไม่สามารถเปิดกล้องได้")

        self.samples = []
        self.last_frame = None

        self.preview = QLabel(
            "กำลังเปิดกล้อง..."
        )

        self.preview.setAlignment(
            Qt.AlignCenter
        )

        self.preview.setMinimumSize(
            640,
            420,
        )

        self.status = QLabel(
            "กรุณามองกล้องเพื่อเก็บใบหน้า 5 ตัวอย่าง"
        )

        self.status.setAlignment(
            Qt.AlignCenter
        )

        self.username_input = QLineEdit()

        self.email_input = QLineEdit()

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.Password)

        form = QFormLayout()

        form.addRow(
            "ชื่อบัญชีสำหรับ Login",
            self.username_input,
        )

        form.addRow(
            "Email",
            self.email_input,
        )

        form.addRow("รหัสผ่าน", self.password_input)
        form.addRow("ยืนยันรหัสผ่าน", self.confirm_password_input)

        self.save_button = QPushButton(
            "Create User"
        )

        self.save_button.setEnabled(
            False
        )

        self.save_button.clicked.connect(
            self.save_user
        )

        layout = QVBoxLayout(
            self
        )

        layout.addWidget(
            self.preview
        )

        layout.addLayout(
            form
        )

        layout.addWidget(
            self.status
        )

        layout.addWidget(
            self.save_button
        )

        self.preview_timer = QTimer(self)
        self.preview_timer.timeout.connect(self.update_preview)
        self.preview_timer.start(80)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.process_frame)
        self.timer.start(settings.login_scan_interval_ms)


    def update_preview(self):
        success, frame = self.camera.read()
        if not success:
            return
        self.last_frame = cv2.flip(frame, 1)
        self.show_frame(self.last_frame)


    def process_frame(self):

        if self.last_frame is None:
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

        if (
            embedding is not None
            and len(self.samples) < 5
        ):

            self.samples.append(
                embedding.copy()
            )

            count = len(
                self.samples
            )

            self.status.setText(
                f"กำลังเก็บใบหน้า "
                f"{count}/5"
            )

            if count >= 5:

                self.save_button.setEnabled(
                    True
                )

                self.status.setText(
                    "เก็บใบหน้าครบแล้ว "
                    "สามารถกด Create User ได้"
                )

        elif embedding is None:
            self.status.setText(self.face_service.last_error or "ไม่พบใบหน้า")


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


    def save_user(self):

        username = (
            self.username_input
            .text()
        )

        email = (
            self.email_input
            .text()
            .strip()
        )

        password = self.password_input.text()

        username_error = validate_username(username)
        if username_error:

            QMessageBox.warning(
                self,
                "ชื่อบัญชีไม่ถูกต้อง",
                username_error,
            )

            return

        password_error = validate_password(password)
        if password_error:
            QMessageBox.warning(self, "รหัสผ่านไม่ปลอดภัย", password_error)
            return
        if password != self.confirm_password_input.text():
            QMessageBox.warning(self, "ข้อมูลไม่ตรงกัน", "การยืนยันรหัสผ่านไม่ตรงกัน")
            return

        if len(self.samples) < 5:

            QMessageBox.warning(
                self,
                "Face",
                "กรุณาเก็บใบหน้าให้ครบ 5 ตัวอย่าง",
            )

            return

        try:

            user = create_user(
                username=username,
                email=email,
                password=password,
            )

            for embedding in self.samples:

                add_face_embedding(
                    user_id=user.id,
                    embedding=embedding,
                )
                self.face_service.cache_embedding(user, embedding)

            self.created_user = user

            # Preserve the already-open camera for Chatbot monitoring. The
            # parent login widget will take ownership after dialog.exec().
            self.camera_handoff = self.camera
            self.camera = None

            self.accept()

        except Exception as error:

            QMessageBox.critical(
                self,
                "Create User failed",
                str(error),
            )


    def closeEvent(
        self,
        event,
    ):

        self.timer.stop()
        self.preview_timer.stop()

        if self.camera:

            self.camera.release()

        event.accept()


    def done(self, result):
        self.timer.stop()
        self.preview_timer.stop()
        if self.camera:
            self.camera.release()
            self.camera = None
        super().done(result)


    def take_camera_for_monitoring(self):
        camera = self.camera_handoff
        self.camera_handoff = None
        return camera
