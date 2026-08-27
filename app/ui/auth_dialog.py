from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QVBoxLayout,
)

from app.repositories import (
    authenticate_user,
    get_user_by_identifier,
    set_user_password,
    verify_current_password,
)
from app.services.password_service import validate_password


class ResetPasswordDialog(QDialog):
    def __init__(self, user, require_current=False, parent=None):
        super().__init__(parent)
        self.user = user
        self.require_current = require_current
        self.setWindowTitle("ตั้งรหัสผ่านใหม่")
        form = QFormLayout()
        self.current = QLineEdit()
        self.current.setEchoMode(QLineEdit.Password)
        if require_current and user.password_hash:
            form.addRow("รหัสผ่านปัจจุบัน", self.current)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.Password)
        form.addRow("รหัสผ่านใหม่", self.password)
        form.addRow("ยืนยันรหัสผ่าน", self.confirm)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("อย่างน้อย 8 ตัวอักษร และต้องมีตัวอักษรกับตัวเลข"))
        layout.addWidget(buttons)

    def save(self):
        if self.require_current and self.user.password_hash:
            if not verify_current_password(self.user.id, self.current.text()):
                QMessageBox.warning(self, "ไม่สำเร็จ", "รหัสผ่านปัจจุบันไม่ถูกต้อง")
                return
        password = self.password.text()
        error = validate_password(password)
        if error:
            QMessageBox.warning(self, "รหัสผ่านไม่ปลอดภัย", error)
            return
        if password != self.confirm.text():
            QMessageBox.warning(self, "ข้อมูลไม่ตรงกัน", "การยืนยันรหัสผ่านไม่ตรงกัน")
            return
        updated = set_user_password(self.user.id, password)
        if updated is None:
            QMessageBox.critical(self, "ไม่สำเร็จ", "ไม่พบบัญชีผู้ใช้")
            return
        self.user = updated
        self.accept()


class PasswordDialog(QDialog):
    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self.authenticated_user = None
        self.setWindowTitle("ยืนยันรหัสผ่าน")
        self.setModal(True)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("รหัสผ่าน")
        self.password.returnPressed.connect(self.login)
        login_button = QPushButton("เข้าสู่ระบบ")
        forgot_button = QPushButton("ลืมรหัสผ่าน")
        login_button.clicked.connect(self.login)
        forgot_button.clicked.connect(self.forgot_password)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"สวัสดี คุณ{user.display_name}\nกรุณากรอกรหัสผ่านเพื่อเข้าสู่ระบบ"))
        layout.addWidget(self.password)
        layout.addWidget(login_button)
        layout.addWidget(forgot_button)
        self.resize(390, 220)

    def login(self):
        user, error = authenticate_user(self.user.id, self.password.text())
        if error:
            QMessageBox.warning(self, "เข้าสู่ระบบไม่สำเร็จ", error)
            self.password.clear()
            return
        self.authenticated_user = user
        self.accept()

    def forgot_password(self):
        # This dialog is reachable only after a fresh, high-confidence face match.
        dialog = ResetPasswordDialog(self.user, require_current=False, parent=self)
        if dialog.exec():
            self.user = dialog.user
            QMessageBox.information(self, "สำเร็จ", "ตั้งรหัสผ่านใหม่แล้ว กรุณาเข้าสู่ระบบ")


class ManualLoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.authenticated_user = None
        self.setWindowTitle("เข้าสู่ระบบด้วยบัญชี")
        self.resize(420, 230)

        self.identifier = QLineEdit()
        self.identifier.setPlaceholderText(
            "ชื่อบัญชีสำหรับ Login หรืออีเมล (ตัวพิมพ์ต้องตรงกัน)"
        )
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("รหัสผ่าน")
        self.password.returnPressed.connect(self.login)

        form = QFormLayout()
        form.addRow("ชื่อบัญชีหรืออีเมล", self.identifier)
        form.addRow("รหัสผ่าน", self.password)

        login_button = QPushButton("เข้าสู่ระบบ")
        cancel_button = QPushButton("ยกเลิก")
        login_button.clicked.connect(self.login)
        cancel_button.clicked.connect(self.reject)

        buttons = QVBoxLayout()
        buttons.addWidget(login_button)
        buttons.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)

    def login(self):
        user = get_user_by_identifier(self.identifier.text())
        if user is None:
            QMessageBox.warning(
                self,
                "เข้าสู่ระบบไม่สำเร็จ",
                "ไม่พบชื่อบัญชีหรืออีเมลนี้ กรุณาตรวจตัวพิมพ์เล็ก–ใหญ่",
            )
            return
        authenticated, error = authenticate_user(user.id, self.password.text())
        if error:
            QMessageBox.warning(self, "เข้าสู่ระบบไม่สำเร็จ", error)
            self.password.clear()
            return
        self.authenticated_user = authenticated
        self.accept()
