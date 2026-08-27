from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QTextEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QFrame,
    QMessageBox,
)

from PySide6.QtCore import QThreadPool

from app.repositories import (
    get_chat_messages,
)

from app.services.chat_service import (
    ChatService,
)

from app.ui.workers import (
    Worker,
)
from app.services.stt_service import WhisperSTTService


class MessageBubble(QLabel):

    def __init__(
        self,
        role,
        text,
    ):

        super().__init__(
            text
        )

        self.setWordWrap(
            True
        )

        self.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        self.setMaximumWidth(
            760
        )

        if role == "user":

            self.setObjectName(
                "messageUser"
            )

        else:

            self.setObjectName(
                "messageModel"
            )


class ChatWidget(QWidget):

    def __init__(
        self,
        user,
        chat_id,
    ):

        super().__init__()

        self.user = user

        self.chat_id = chat_id

        self.thread_pool = (
            QThreadPool.globalInstance()
        )

        self.chat_service = None

        self.scroll = QScrollArea()

        self.scroll.setWidgetResizable(
            True
        )

        self.scroll.setFrameShape(
            QFrame.NoFrame
        )

        self.messages_container = (
            QWidget()
        )

        self.messages_layout = (
            QVBoxLayout(
                self.messages_container
            )
        )

        self.messages_layout.addStretch()

        self.scroll.setWidget(
            self.messages_container
        )

        self.input = QTextEdit()

        self.input.setObjectName(
            "messageInput"
        )

        self.input.setPlaceholderText(
            "ส่งข้อความถึง Gemini..."
        )

        self.input.setMaximumHeight(
            130
        )

        self.send_button = QPushButton(
            "Send"
        )

        self.send_button.clicked.connect(
            self.send_message
        )

        self.mic_button = QPushButton("🎤")
        self.mic_button.setToolTip("พูดข้อความ (บันทึก 6 วินาที)")
        self.mic_button.clicked.connect(self.start_voice_input)

        bottom_layout = QHBoxLayout()

        bottom_layout.addWidget(
            self.input,
            1,
        )

        bottom_layout.addWidget(self.mic_button)

        bottom_layout.addWidget(
            self.send_button
        )

        layout = QVBoxLayout(
            self
        )

        layout.addWidget(
            self.scroll,
            1,
        )

        layout.addLayout(
            bottom_layout
        )

        self.load_history()


    def start_voice_input(self):
        self.mic_button.setEnabled(False)
        self.mic_button.setText("●")
        self.input.setPlaceholderText("กำลังฟังเสียง...")
        worker = Worker(lambda: WhisperSTTService().transcribe())
        worker.signals.finished.connect(self.on_transcript)
        worker.signals.error.connect(self.on_stt_error)
        self.thread_pool.start(worker)


    def on_transcript(self, text):
        current = self.input.toPlainText().strip()
        self.input.setPlainText((current + " " + text).strip())
        self.mic_button.setEnabled(True)
        self.mic_button.setText("🎤")
        self.input.setPlaceholderText("ส่งข้อความถึง Gemini...")
        self.input.setFocus()


    def on_stt_error(self, error):
        self.mic_button.setEnabled(True)
        self.mic_button.setText("🎤")
        self.input.setPlaceholderText("ส่งข้อความถึง Gemini...")
        QMessageBox.warning(self, "รับเสียงไม่สำเร็จ", error)


    def load_history(self):

        messages = (
            get_chat_messages(
                chat_id=self.chat_id,
                user_id=self.user.id,
            )
        )

        for message in messages:

            self.add_message_bubble(
                role=message.role,
                text=message.content,
            )


    def add_message_bubble(
        self,
        role,
        text,
    ):

        row = QHBoxLayout()

        bubble = MessageBubble(
            role,
            text,
        )

        if role == "user":

            row.addStretch()

            row.addWidget(
                bubble
            )

        else:

            row.addWidget(
                bubble
            )

            row.addStretch()

        self.messages_layout.insertLayout(
            self.messages_layout.count() - 1,
            row,
        )


    def send_message(self):

        text = (
            self.input
            .toPlainText()
            .strip()
        )

        if not text:
            return

        self.input.clear()

        self.add_message_bubble(
            "user",
            text,
        )

        self.send_button.setEnabled(
            False
        )

        self.input.setEnabled(
            False
        )

        def task():

            service = (
                self.chat_service
                or ChatService()
            )

            self.chat_service = service

            return service.send_message(
                user_id=self.user.id,
                chat_id=self.chat_id,
                text=text,
            )

        worker = Worker(
            task
        )

        worker.signals.finished.connect(
            self.on_answer
        )

        worker.signals.error.connect(
            self.on_error
        )

        self.thread_pool.start(
            worker
        )


    def on_answer(
        self,
        answer,
    ):

        self.add_message_bubble(
            "model",
            answer,
        )

        self.send_button.setEnabled(
            True
        )

        self.input.setEnabled(
            True
        )

        self.input.setFocus()


    def on_error(
        self,
        error,
    ):

        QMessageBox.critical(
            self,
            "Gemini Error",
            error,
        )

        self.send_button.setEnabled(
            True
        )

        self.input.setEnabled(
            True
        )
