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
    QDialog,
)

from app.repositories import (
    get_user_chats,
    create_chat,
    delete_chat,
    get_user,
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
from app.services.face_service import FaceService
from app.services.presence_service import (
    FacePresenceMonitor,
    LOGOUT_COUNTDOWN_SECONDS,
    MonitorAction,
    NORMAL_SCAN_INTERVAL,
    SessionMonitorState,
    SWITCH_VERIFY_INTERVAL,
    WARNING_SCAN_INTERVAL,
)
from app.services.tts_service import ThaiTTSService
from app.ui.settings_dialog import SettingsDialog
from app.ui.workers import Worker


class LogoutWarningDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.allow_close = False
        self.setWindowTitle("กำลังออกจากระบบ")
        self.setModal(True)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.resize(390, 230)

        title = QLabel("กำลังออกจากระบบ")
        title.setAlignment(Qt.AlignCenter)
        self.countdown_label = QLabel(str(LOGOUT_COUNTDOWN_SECONDS))
        self.countdown_label.setAlignment(Qt.AlignCenter)
        self.countdown_label.setStyleSheet("font-size: 46px; font-weight: 700;")
        message = QLabel("กรุณามองกล้องเพื่อใช้งานต่อ")
        message.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.countdown_label)
        layout.addWidget(message)

    def set_countdown(self, seconds):
        self.countdown_label.setText(str(seconds))

    def close_safely(self):
        self.allow_close = True
        self.accept()

    def reject(self):
        if self.allow_close:
            super().reject()

    def closeEvent(self, event):
        if self.allow_close:
            event.accept()
        else:
            event.ignore()


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
        self.face_service = None
        self.pending_monitor_camera = None
        self.welcome_audio_ready = False

        self.chat_widgets = {}
        self.presence_monitor = None
        self.session_monitor_state = None
        self.warning_dialog = None
        self.warning_timer = QTimer(self)
        self.warning_timer.timeout.connect(self.update_logout_countdown)
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

        QMessageBox.warning(
            self,
            "กล้องไม่พร้อมใช้งาน",
            f"{error}\nยังสามารถเข้าสู่ระบบด้วยบัญชีหรืออีเมลได้",
        )


    def on_login(
        self,
        user,
    ):

        self.face_service = getattr(self.login_widget, "face_service", None)
        take_camera = getattr(
            self.login_widget,
            "take_camera_for_monitoring",
            None,
        )
        login_camera = take_camera() if take_camera is not None else None
        self.welcome_audio_ready = False

        self.current_user = user
        FaceService.update_cached_user(user)
        self.session_monitor_state = SessionMonitorState(user.id)

        # Start the monitoring thread before building/loading the chat page.
        # VideoCapture can therefore open while the UI and chat history load.
        if bool(getattr(user, "camera_enabled", True)):
            self.pending_monitor_camera = login_camera
            self.start_presence_monitor()
        elif login_camera is not None:
            login_camera.release()

        self.build_chat_interface()

        self.load_chats()

        # TTS synthesis can be slow. It must never delay camera startup or UI.
        if bool(getattr(user, "speaker_enabled", True)):
            self.prepare_welcome_in_background(user)


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

        for widget in self.chat_widgets.values():
            self.chat_stack.removeWidget(widget)
            widget.deleteLater()
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

        FaceService.update_cached_user(self.current_user)

        self.update_profile_button()


    def open_settings(self):
        dialog = SettingsDialog(self.current_user, self)
        if dialog.exec():
            self.current_user = dialog.user
            FaceService.update_cached_user(self.current_user)
            microphone_enabled = bool(
                getattr(self.current_user, "microphone_enabled", True)
            )
            for widget in self.chat_widgets.values():
                widget.user = self.current_user
                widget.set_microphone_enabled(microphone_enabled)

            if bool(getattr(self.current_user, "camera_enabled", True)):
                if self.presence_monitor is None:
                    if self.session_monitor_state is None:
                        self.session_monitor_state = SessionMonitorState(
                            self.current_user.id
                        )
                    self.start_presence_monitor()
            else:
                self.cancel_logout_warning()
                self.stop_presence_monitor()
                if self.session_monitor_state is not None:
                    self.session_monitor_state.reset_all()


    def play_welcome(self):
        if (
            self.current_user is None
            or not self.welcome_audio_ready
            or not bool(getattr(self.current_user, "speaker_enabled", True))
        ):
            return
        worker = Worker(lambda: ThaiTTSService().play_prepared())
        worker.signals.error.connect(
            lambda error: QMessageBox.warning(self, "TTS Error", error)
        )
        self.thread_pool.start(worker)


    def prepare_welcome_in_background(self, user):
        user_id = user.id
        welcome = f"ยินดีต้อนรับค่ะ คุณ{user.display_name}"

        def task():
            ThaiTTSService().prepare_text(welcome)
            return user_id

        worker = Worker(task)
        worker.signals.finished.connect(self.on_welcome_prepared)
        worker.signals.error.connect(
            lambda error, expected_user_id=user_id: self.on_welcome_error(
                expected_user_id,
                error,
            )
        )
        self.thread_pool.start(worker)


    def on_welcome_prepared(self, user_id):
        if (
            self.current_user is None
            or self.current_user.id != user_id
            or not bool(getattr(self.current_user, "speaker_enabled", True))
        ):
            return
        self.welcome_audio_ready = True
        self.play_welcome()


    def on_welcome_error(self, user_id, error):
        if self.current_user is None or self.current_user.id != user_id:
            return
        QMessageBox.warning(
            self,
            "ลำโพงไม่พร้อมใช้งาน",
            f"ไม่สามารถเตรียมเสียงต้อนรับได้ แต่ยังใช้งาน Chatbot ได้\n{error}",
        )


    def logout_current_user(self):
        self.cancel_logout_warning()
        self.stop_presence_monitor()

        if self.session_monitor_state is not None:
            self.session_monitor_state.reset_all()
        self.session_monitor_state = None

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


    def logout(self):
        self.logout_current_user()


    def start_presence_monitor(self):
        if (
            self.current_user is None
            or not bool(getattr(self.current_user, "camera_enabled", True))
        ):
            return
        self.stop_presence_monitor()
        # Login has already prepared InsightFace. Reuse that instance after
        # FaceLoginWidget stopped its camera to avoid a second model load.
        self.presence_monitor = FacePresenceMonitor(
            self.current_user.id,
            self,
            face_service=self.face_service,
            camera=self.pending_monitor_camera,
        )
        self.pending_monitor_camera = None
        self.presence_monitor.scan_result.connect(self.on_face_scan_result)
        self.presence_monitor.error.connect(self.on_presence_error)
        self.presence_monitor.start()


    def stop_presence_monitor(self):
        if self.presence_monitor is not None:
            self.presence_monitor.stop()
            self.presence_monitor.deleteLater()
            self.presence_monitor = None


    def on_face_scan_result(self, result):
        if self.current_user is None or self.session_monitor_state is None:
            return

        decision = self.session_monitor_state.process(result)

        if decision.action == MonitorAction.CONTINUE:
            self.cancel_logout_warning()
            self.presence_monitor.set_interval(NORMAL_SCAN_INTERVAL)
            return

        if decision.action == MonitorAction.NO_FACE:
            self.presence_monitor.set_interval(NORMAL_SCAN_INTERVAL)
            return

        if decision.action == MonitorAction.SHOW_WARNING:
            self.show_logout_warning()
            self.presence_monitor.set_interval(WARNING_SCAN_INTERVAL)
            return

        if decision.action == MonitorAction.VERIFY_SWITCH:
            self.presence_monitor.set_interval(SWITCH_VERIFY_INTERVAL)
            return

        if decision.action == MonitorAction.SWITCH_USER:
            self.switch_current_user(decision.user)
            return

        if decision.action == MonitorAction.LOGOUT_IMMEDIATELY:
            self.logout_current_user()
            return

    def show_logout_warning(self):
        if self.warning_dialog is not None:
            return
        self.session_monitor_state.countdown_seconds = LOGOUT_COUNTDOWN_SECONDS
        self.warning_dialog = LogoutWarningDialog(self)
        self.warning_dialog.set_countdown(LOGOUT_COUNTDOWN_SECONDS)
        self.warning_dialog.show()
        self.warning_dialog.raise_()
        self.warning_dialog.activateWindow()
        self.warning_timer.start(1000)


    def update_logout_countdown(self):
        if self.warning_dialog is None or self.session_monitor_state is None:
            self.warning_timer.stop()
            return
        self.session_monitor_state.countdown_seconds -= 1
        seconds = max(0, self.session_monitor_state.countdown_seconds)
        self.warning_dialog.set_countdown(seconds)
        if seconds == 0:
            self.warning_timer.stop()
            QTimer.singleShot(0, self.finish_countdown_logout)


    def finish_countdown_logout(self):
        if self.warning_dialog is not None and self.current_user is not None:
            self.logout_current_user()


    def cancel_logout_warning(self):
        self.warning_timer.stop()
        if self.warning_dialog is not None:
            dialog = self.warning_dialog
            self.warning_dialog = None
            dialog.close_safely()
            dialog.deleteLater()
        if self.session_monitor_state is not None:
            self.session_monitor_state.countdown_seconds = LOGOUT_COUNTDOWN_SECONDS


    def switch_current_user(self, cached_user):
        if cached_user is None or self.current_user is None:
            return
        user = get_user(cached_user.id) or cached_user
        self.cancel_logout_warning()
        self.current_user = user
        FaceService.update_cached_user(user)
        self.session_monitor_state.reset_all(current_user_id=user.id)
        if bool(getattr(user, "camera_enabled", True)):
            if self.presence_monitor is not None:
                self.presence_monitor.set_current_user(user.id)
                self.presence_monitor.set_interval(NORMAL_SCAN_INTERVAL)
            else:
                self.start_presence_monitor()
        else:
            self.stop_presence_monitor()
        self.update_profile_button()
        self.load_chats()


    def on_presence_error(self, error):
        self.stop_presence_monitor()
        self.cancel_logout_warning()
        if self.session_monitor_state is not None:
            self.session_monitor_state.reset_all()
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
