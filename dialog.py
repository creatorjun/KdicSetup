from PyQt6.QtWidgets import (QDialog, QLineEdit, QDialogButtonBox,
                             QLabel, QVBoxLayout, QMessageBox)
from PyQt6.QtCore import QTimer

def show_message_box(level: str, title: str, message: str, parent=None):
    if level == 'info':
        QMessageBox.information(parent, title, message)
    elif level == 'warning':
        QMessageBox.warning(parent, title, message)
    elif level == 'critical':
        QMessageBox.critical(parent, title, message)
    else:
        QMessageBox.information(parent, title, message)

class ConfirmationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("데이터 삭제 확인")
        self.setModal(True)

        layout = QVBoxLayout(self)
        
        message = QLabel("모든 데이터가 영구적으로 삭제됩니다.\n데이터를 삭제하려면 '960601'을 입력하세요.")
        layout.addWidget(message)

        self.input_field = QLineEdit()
        self.input_field.textChanged.connect(self._validate_input)
        layout.addWidget(self.input_field)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        self.ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(False)
        
        layout.addWidget(self.button_box)

    def _validate_input(self, text: str):
        if text == "960601":
            self.ok_button.setEnabled(True)
        else:
            self.ok_button.setEnabled(False)

class RebootDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("작업 완료")
        self.setModal(True)
        self.resize(350, 150)
        
        self.countdown = 10
        
        layout = QVBoxLayout(self)
        self.message_label = QLabel()
        layout.addWidget(self.message_label)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText("지금 재시작")
        
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_countdown)
        self.timer.start(1000)
        
        self._update_countdown()

    def _update_countdown(self):
        if self.countdown > 0:
            self.message_label.setText(f"모든 작업이 완료되었습니다.\n{self.countdown}초 후 시스템을 재시작합니다.")
            self.countdown -= 1
        else:
            self.timer.stop()
            self.accept()

    def accept(self):
        self.timer.stop()
        super().accept()

    def reject(self):
        self.timer.stop()
        super().reject()