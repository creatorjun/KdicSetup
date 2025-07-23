# dialog.py

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QListWidget, 
                             QListWidgetItem, QDialogButtonBox, QLabel, QLineEdit)
from PyQt5.QtCore import Qt

class SelectDataPartitionDialog(QDialog):
    """데이터 파티션 선택을 위한 커스텀 다이얼로그"""
    def __init__(self, partitions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("데이터 파티션 선택")
        self.setMinimumWidth(350)
        
        self.selected_partition = None
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        for p in partitions:
            # 리스트 위젯에 표시될 텍스트와 실제 데이터(볼륨 번호)를 함께 저장
            item_text = f"드라이브: {p['letter']} (수정된 날짜: {p['date']})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, p['number']) # 사용자 역할 데이터로 볼륨 번호 저장
            self.list_widget.addItem(item)
        
        self.list_widget.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.list_widget)

        # OK, Cancel 버튼
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # 처음엔 OK 버튼 비활성화
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(False) 

    def on_selection_changed(self):
        """리스트에서 항목 선택 시 OK 버튼 활성화"""
        if self.list_widget.selectedItems():
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)
            # 선택된 아이템의 볼륨 번호를 저장
            self.selected_partition = self.list_widget.selectedItems()[0].data(Qt.UserRole)

class ConfirmDeleteDialog(QDialog):
    """'y'를 입력해야 확인되는 데이터 삭제 확인 다이얼로그"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("경고")
        layout = QVBoxLayout(self)

        message_label = QLabel("모든 데이터가 삭제 됩니다.\n진행하려면 'y'를 입력하세요.", self)
        layout.addWidget(message_label)

        self.input_line = QLineEdit(self)
        self.input_line.textChanged.connect(self.on_text_changed)
        layout.addWidget(self.input_line)

        # Cancel 버튼만 있는 버튼 박스
        self.button_box = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def on_text_changed(self, text):
        """입력 텍스트가 'y'이면 다이얼로그를 수락(accept)"""
        if text.lower() == 'y' or text() == 'ㅛ':
            self.accept()