from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.repositories import update_user_settings


class SettingsDialog(QDialog):
    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle("ตั้งค่า")
        self.resize(600, 430)

        user_button = QPushButton("ผู้ใช้")
        user_button.setEnabled(False)
        user_button.setFixedWidth(130)

        content = QFrame()
        content_layout = QVBoxLayout(content)
        title = QLabel("การเข้าสู่ระบบของผู้ใช้")
        title.setObjectName("settingsTitle")
        self.require_password = QCheckBox(
            "ให้ป้อนรหัสผ่านหลัง Face Recognition"
        )
        self.require_password.setChecked(
            bool(user.require_password_after_face)
        )
        description = QLabel(
            "เปิดใช้เฉพาะบัญชีนี้เท่านั้น บัญชีอื่นจะเข้าหน้า Chatbot "
            "ทันทีหลังจดจำใบหน้าสำเร็จ"
        )
        description.setWordWrap(True)
        device_title = QLabel("อุปกรณ์")
        device_title.setObjectName("settingsTitle")
        self.camera_enabled = QCheckBox("เปิดกล้องตรวจสอบผู้ใช้ในหน้า Chatbot")
        self.microphone_enabled = QCheckBox("เปิดไมโครโฟนสำหรับพิมพ์ด้วยเสียง")
        self.speaker_enabled = QCheckBox("เปิดลำโพงสำหรับเสียงต้อนรับ")
        self.camera_enabled.setChecked(bool(getattr(user, "camera_enabled", True)))
        self.microphone_enabled.setChecked(
            bool(getattr(user, "microphone_enabled", True))
        )
        self.speaker_enabled.setChecked(bool(getattr(user, "speaker_enabled", True)))
        for switch in (
            self.require_password,
            self.camera_enabled,
            self.microphone_enabled,
            self.speaker_enabled,
        ):
            switch.setObjectName("settingsSwitch")
        self.setStyleSheet(
            """
            QCheckBox#settingsSwitch::indicator { width: 42px; height: 22px; }
            QCheckBox#settingsSwitch::indicator:unchecked {
                border-radius: 11px; background: #555555;
            }
            QCheckBox#settingsSwitch::indicator:checked {
                border-radius: 11px; background: #19c37d;
            }
            """
        )
        content_layout.addWidget(title)
        content_layout.addWidget(self.require_password)
        content_layout.addWidget(description)
        content_layout.addSpacing(14)
        content_layout.addWidget(device_title)
        content_layout.addWidget(self.camera_enabled)
        content_layout.addWidget(self.microphone_enabled)
        content_layout.addWidget(self.speaker_enabled)
        content_layout.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        content_layout.addWidget(buttons)

        layout = QHBoxLayout(self)
        layout.addWidget(user_button)
        layout.addWidget(content, 1)

    def save(self):
        if self.require_password.isChecked() and not self.user.password_hash:
            QMessageBox.warning(
                self,
                "ยังไม่มีรหัสผ่าน",
                "กรุณาตั้งรหัสผ่านใน Profile ก่อนเปิดตัวเลือกนี้",
            )
            return
        updated = update_user_settings(
            self.user.id,
            self.require_password.isChecked(),
            self.camera_enabled.isChecked(),
            self.microphone_enabled.isChecked(),
            self.speaker_enabled.isChecked(),
        )
        if updated is None:
            QMessageBox.critical(self, "บันทึกไม่สำเร็จ", "ไม่พบบัญชีผู้ใช้")
            return
        self.user = updated
        self.accept()
