from PySide6.QtWidgets import (
    QDialog,
    QLineEdit,
    QPushButton,
    QFormLayout,
    QVBoxLayout,
    QMessageBox,
)

from app.repositories import (
    update_user,
)
from app.ui.auth_dialog import ResetPasswordDialog


class ProfileDialog(QDialog):

    def __init__(
        self,
        user,
    ):

        super().__init__()

        self.user = user

        self.logout_requested = False

        self.setWindowTitle(
            "Profile"
        )

        self.resize(
            400,
            250,
        )

        self.username_input = (
            QLineEdit(
                user.username
            )
        )

        self.email_input = QLineEdit(
            user.email or ""
        )

        form = QFormLayout()

        form.addRow(
            "ชื่อบัญชี / ชื่อที่แสดง",
            self.username_input,
        )

        form.addRow(
            "Email",
            self.email_input,
        )

        self.save_button = QPushButton(
            "Save"
        )

        self.logout_button = QPushButton(
            "Logout"
        )

        self.forgot_button = QPushButton("ลืมรหัสผ่าน / เปลี่ยนรหัสผ่าน")

        self.save_button.clicked.connect(
            self.save
        )

        self.logout_button.clicked.connect(
            self.logout
        )
        self.forgot_button.clicked.connect(self.reset_password)

        layout = QVBoxLayout(
            self
        )

        layout.addLayout(
            form
        )

        layout.addWidget(
            self.save_button
        )

        layout.addWidget(self.forgot_button)

        layout.addWidget(
            self.logout_button
        )


    def save(self):

        try:
            updated_user = update_user(
                user_id=self.user.id,
                username=self.username_input.text(),
                email=self.email_input.text(),
            )
        except ValueError as error:
            QMessageBox.warning(self, "ชื่อบัญชีไม่ถูกต้อง", str(error))
            return

        if updated_user:

            self.user = updated_user

            self.accept()


    def logout(self):

        self.logout_requested = True

        self.reject()


    def reset_password(self):
        # The user has already passed face + password authentication and the
        # presence monitor is active while this profile dialog is open.
        dialog = ResetPasswordDialog(self.user, require_current=False, parent=self)
        if dialog.exec():
            self.user = dialog.user
