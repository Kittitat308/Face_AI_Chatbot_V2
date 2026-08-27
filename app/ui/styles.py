APP_STYLE = """
QMainWindow,
QWidget {
    background-color: #212121;
    color: #ececec;
    font-family: "Segoe UI";
    font-size: 14px;
}

QFrame#sidebar {
    background-color: #171717;
}

QLabel#appTitle {
    font-size: 18px;
    font-weight: 700;
}

QPushButton {
    background-color: #2f2f2f;
    color: #f2f2f2;
    border: none;
    border-radius: 8px;
    padding: 9px 12px;
}

QPushButton:hover {
    background-color: #3b3b3b;
}

QPushButton#newChat {
    text-align: left;
}

QListWidget {
    background-color: transparent;
    border: none;
    outline: none;
}

QListWidget::item {
    padding: 11px;
    border-radius: 7px;
}

QListWidget::item:selected {
    background-color: #2f2f2f;
}

QLineEdit,
QTextEdit {
    background-color: #2f2f2f;
    color: #f2f2f2;
    border: 1px solid #444444;
    border-radius: 12px;
    padding: 10px;
}

QTextEdit#messageInput {
    padding: 14px;
}

QLabel#messageUser {
    background-color: #2f2f2f;
    border-radius: 12px;
    padding: 12px;
}

QLabel#messageModel {
    background-color: transparent;
    padding: 12px;
}

QDialog {
    background-color: #212121;
}
"""