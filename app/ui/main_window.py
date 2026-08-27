from PySide6.QtCore import QThreadPool, QTimer, Qt

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QMessageBox,
)

from app.repositories import (
    get_user_chats,
    create_chat,
    delete_chat,
)

from app.ui.face_login import (
    FaceLoginWidget,
)

from app.ui.chat_widget import (
    ChatWidget,
)

from app.ui.profile_dialog import (
    ProfileDialog,
)

from app.ui.styles import (
    APP_STYLE,
)
from app.services.presence_service import FacePresenceMonitor
from app.services.tts_service import ThaiTTSService
from app.ui.settings_dialog import SettingsDialog
from app.ui.workers import Worker


class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            "Face AI Chatbot"
        )

        self.resize(
            1280,
            820,
        )

        self.setStyleSheet(
            APP_STYLE
        )

        self.current_user = None

        self.chat_widgets = {}
        self.presence_monitor = None
        self.thread_pool = QThreadPool.globalInstance()

        self.login_widget = (
            FaceLoginWidget()
        )

        self.login_widget.logged_in.connect(
            self.on_login
        )

        self.login_widget.camera_error.connect(
            self.on_camera_error
        )

        self.setCentralWidget(
            self.login_widget
        )

        self.login_widget.start()


    def on_camera_error(
        self,
        error,
    ):

        QMessageBox.critical(
            self,
            "Camera / Face Recognition Error",
            error,
        )


    def on_login(
        self,
        user,
    ):

        welcome = f"ยินดีต้อนรับค่ะ คุณ{user.display_name}"
        try:
            ThaiTTSService().prepare_text(welcome)
        except Exception as error:
            QMessageBox.critical(
                self,
                "TTS Error",
                f"ไม่สามารถเตรียมเสียงต้อนรับได้\n{error}",
            )
            if getattr(self, "login_widget", None) is not None:
                self.login_widget.start()
            return

        self.current_user = user

        self.build_chat_interface()

        self.load_chats()

        QTimer.singleShot(100, self.play_welcome)

        # Let the Chatbot page render and the welcome voice start first.
        QTimer.singleShot(250, self.start_presence_monitor)


    def build_chat_interface(self):

        root = QWidget()

        root_layout = QHBoxLayout(
            root
        )

        root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        root_layout.setSpacing(
            0
        )

        sidebar = QFrame()

        sidebar.setObjectName(
            "sidebar"
        )

        sidebar.setFixedWidth(
            290
        )

        sidebar_layout = QVBoxLayout(
            sidebar
        )

        sidebar_layout.setContentsMargins(
            12,
            16,
            12,
            12,
        )

        title = QLabel(
            "Face AI Chatbot"
        )

        title.setObjectName(
            "appTitle"
        )

        sidebar_layout.addWidget(
            title
        )

        self.new_chat_button = (
            QPushButton(
                "+  New chat"
            )
        )

        self.new_chat_button.setObjectName(
            "newChat"
        )

        self.new_chat_button.clicked.connect(
            self.create_new_chat
        )

        self.delete_chat_button = QPushButton("🗑")
        self.delete_chat_button.setToolTip("ลบแชทที่เลือก")
        self.delete_chat_button.clicked.connect(self.delete_selected_chat)
        chat_actions = QHBoxLayout()
        chat_actions.addWidget(self.new_chat_button, 1)
        chat_actions.addWidget(self.delete_chat_button)
        sidebar_layout.addLayout(chat_actions)

        self.chat_list = QListWidget()

        self.chat_list.currentRowChanged.connect(
            self.open_chat
        )

        sidebar_layout.addWidget(
            self.chat_list,
            1,
        )

        self.settings_button = QPushButton("⚙  ตั้งค่า")
        self.settings_button.clicked.connect(self.open_settings)
        sidebar_layout.addWidget(self.settings_button)

        self.profile_button = QPushButton()

        self.profile_button.clicked.connect(
            self.open_profile
        )

        sidebar_layout.addWidget(
            self.profile_button
        )

        self.update_profile_button()

        self.chat_stack = (
            QStackedWidget()
        )

        root_layout.addWidget(
            sidebar
        )

        root_layout.addWidget(
            self.chat_stack,
            1,
        )

        self.setCentralWidget(
            root
        )
        self.login_widget = None


    def update_profile_button(self):

        self.profile_button.setText(
            f"◉  "
            f"{self.current_user.display_name}"
        )


    def load_chats(self):

        self.chat_list.blockSignals(
            True
        )

        self.chat_list.clear()

        self.chat_widgets.clear()

        chats = get_user_chats(
            self.current_user.id
        )

        if not chats:

            chat = create_chat(
                self.current_user.id
            )

            chats = [
                chat
            ]

        for chat in chats:

            item = QListWidgetItem(
                chat.title
            )

            item.setData(
                Qt.UserRole,
                chat.id,
            )

            self.chat_list.addItem(
                item
            )

        self.chat_list.blockSignals(
            False
        )

        if self.chat_list.count():

            self.chat_list.setCurrentRow(
                0
            )


    def create_new_chat(self):

        chat = create_chat(
            self.current_user.id
        )

        item = QListWidgetItem(
            chat.title
        )

        item.setData(
            Qt.UserRole,
            chat.id,
        )

        self.chat_list.insertItem(
            0,
            item,
        )

        self.chat_list.setCurrentRow(
            0
        )


    def delete_selected_chat(self):
        row = self.chat_list.currentRow()
        item = self.chat_list.item(row) if row >= 0 else None
        if item is None:
            return
        answer = QMessageBox.question(
            self, "ลบแชท", f"ต้องการลบแชท “{item.text()}” ใช่หรือไม่?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        chat_id = item.data(Qt.UserRole)
        if not delete_chat(chat_id, self.current_user.id):
            QMessageBox.warning(self, "ลบไม่สำเร็จ", "ไม่พบแชทนี้")
            return
        widget = self.chat_widgets.pop(chat_id, None)
        if widget is not None:
            self.chat_stack.removeWidget(widget)
            widget.deleteLater()
        self.chat_list.takeItem(row)
        if self.chat_list.count() == 0:
            self.create_new_chat()
        else:
            self.chat_list.setCurrentRow(min(row, self.chat_list.count() - 1))


    def open_chat(
        self,
        row,
    ):

        if row < 0:
            return

        item = self.chat_list.item(
            row
        )

        if item is None:
            return

        chat_id = item.data(
            Qt.UserRole
        )

        if chat_id not in self.chat_widgets:

            widget = ChatWidget(
                user=self.current_user,
                chat_id=chat_id,
            )

            self.chat_widgets[
                chat_id
            ] = widget

            self.chat_stack.addWidget(
                widget
            )

        self.chat_stack.setCurrentWidget(
            self.chat_widgets[
                chat_id
            ]
        )


    def open_profile(self):

        dialog = ProfileDialog(
            self.current_user
        )

        dialog.exec()

        if dialog.logout_requested:

            self.logout()

            return

        self.current_user = (
            dialog.user
        )

        self.update_profile_button()


    def open_settings(self):
        dialog = SettingsDialog(self.current_user, self)
        if dialog.exec():
            self.current_user = dialog.user


    def play_welcome(self):
        if self.current_user is None:
            return
        worker = Worker(lambda: ThaiTTSService().play_prepared())
        worker.signals.error.connect(
            lambda error: QMessageBox.warning(self, "TTS Error", error)
        )
        self.thread_pool.start(worker)


    def logout(self):

        self.stop_presence_monitor()

        self.current_user = None

        self.chat_widgets.clear()

        self.chat_stack.deleteLater()

        self.login_widget = (
            FaceLoginWidget()
        )

        self.login_widget.logged_in.connect(
            self.on_login
        )

        self.login_widget.camera_error.connect(
            self.on_camera_error
        )

        self.setCentralWidget(
            self.login_widget
        )

        self.login_widget.start()


    def start_presence_monitor(self):
        if self.current_user is None:
            return
        self.stop_presence_monitor()
        self.presence_monitor = FacePresenceMonitor(self.current_user.id, self)
        self.presence_monitor.identity_lost.connect(self.on_identity_lost)
        self.presence_monitor.error.connect(self.on_presence_error)
        self.presence_monitor.start()


    def stop_presence_monitor(self):
        if self.presence_monitor is not None:
            self.presence_monitor.stop()
            self.presence_monitor.deleteLater()
            self.presence_monitor = None


    def on_identity_lost(self, other_user):
        if self.current_user is None:
            return
        self.stop_presence_monitor()
        if other_user is None:
            message = "ไม่พบใบหน้าของผู้ใช้ปัจจุบัน ระบบออกจากระบบแล้ว"
        else:
            message = f"ตรวจพบผู้ใช้อื่น ({other_user.display_name}) ระบบออกจากระบบเพื่อยืนยันตัวตนใหม่"
        QMessageBox.warning(self, "ออกจากระบบอัตโนมัติ", message)
        self.logout()


    def on_presence_error(self, error):
        self.stop_presence_monitor()
        QMessageBox.warning(
            self,
            "กล้องไม่พร้อมใช้งาน",
            f"{error}\nระบบออกจากระบบอัตโนมัติถูกปิด แต่ยังใช้งาน Chatbot ต่อได้",
        )


    def closeEvent(
        self,
        event,
    ):

        if getattr(self, "login_widget", None) is not None:
            self.login_widget.stop()

        self.stop_presence_monitor()

        event.accept()
