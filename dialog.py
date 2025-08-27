# dialog.py

# PyQt6.QtWidgets 모듈에서 대화상자(Dialog) 및 관련 위젯들을 가져옵니다.
from PyQt6.QtWidgets import (
    QDialog,
    QLineEdit,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QMessageBox,
)

# PyQt6.QtCore 모듈에서 QTimer 클래스를 가져옵니다.
# QTimer: 일정 시간 간격으로 특정 동작을 실행하게 해주는 타이머입니다.
from PyQt6.QtCore import QTimer


def show_message_box(level: str, title: str, message: str, parent=None):
    """
    간단한 정보, 경고, 오류 메시지를 표시하는 메시지 상자를 보여주는 헬퍼 함수입니다.
    (현재 이 프로젝트에서는 직접적으로 사용되고 있지는 않지만, 유틸리티 함수로 정의되어 있습니다.)

    Args:
        level (str): 메시지 박스의 종류 ('info', 'warning', 'critical').
        title (str): 메시지 박스 창의 제목.
        message (str): 표시할 메시지 내용.
        parent (QWidget, optional): 부모 위젯. Defaults to None.
    """
    if level == "info":
        QMessageBox.information(parent, title, message)
    elif level == "warning":
        QMessageBox.warning(parent, title, message)
    elif level == "critical":
        QMessageBox.critical(parent, title, message)
    else:  # 기본값은 정보 메시지 박스
        QMessageBox.information(parent, title, message)


class ConfirmationDialog(QDialog):
    """
    '데이터 보존' 옵션을 선택하지 않았을 때, 사용자에게 데이터 삭제를 재확인받기 위한 대화상자 클래스입니다.
    특정 문자열('960601')을 입력해야만 'OK' 버튼이 활성화됩니다.
    """

    def __init__(self, parent=None):
        """ConfirmationDialog 클래스의 생성자입니다."""
        # 부모 클래스(QDialog)의 생성자를 호출합니다.
        super().__init__(parent)
        # 대화상자 창의 제목을 설정합니다.
        self.setWindowTitle("데이터 삭제 확인")
        # setModal(True): 이 대화상자가 떠 있는 동안 다른 창과 상호작용할 수 없도록 설정합니다.
        self.setModal(True)

        # 위젯들을 수직으로 배치하기 위한 QVBoxLayout을 생성합니다.
        layout = QVBoxLayout(self)

        # 안내 메시지를 표시할 QLabel 위젯을 생성합니다.
        message = QLabel(
            "모든 데이터가 영구적으로 삭제됩니다.\n데이터를 삭제하려면 '960601'을 입력하세요."
        )
        layout.addWidget(message)

        # 사용자 입력을 받을 QLineEdit(한 줄 텍스트 상자) 위젯을 생성합니다.
        self.input_field = QLineEdit()
        # 입력 필드의 텍스트가 변경될 때마다 _validate_input 메서드가 호출되도록 시그널을 연결합니다.
        self.input_field.textChanged.connect(self._validate_input)
        layout.addWidget(self.input_field)

        # 표준 버튼('OK', 'Cancel')을 포함하는 QDialogButtonBox를 생성합니다.
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        # 'OK' 버튼이 클릭되면 accept() 슬롯이 호출되어 대화상자가 닫히고 QDialog.Accepted를 반환합니다.
        self.button_box.accepted.connect(self.accept)
        # 'Cancel' 버튼이 클릭되면 reject() 슬롯이 호출되어 대화상자가 닫히고 QDialog.Rejected를 반환합니다.
        self.button_box.rejected.connect(self.reject)

        # 버튼 박스에서 'OK' 버튼에 해당하는 포인터를 가져옵니다.
        self.ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        # 초기에는 'OK' 버튼을 비활성화 상태로 설정합니다.
        self.ok_button.setEnabled(False)

        layout.addWidget(self.button_box)

    def _validate_input(self, text: str):
        """사용자가 입력한 텍스트를 검증하여 'OK' 버튼의 활성화 여부를 결정하는 슬롯입니다."""
        # 입력된 텍스트가 "960601"과 일치하는지 확인합니다.
        if text == "960601":
            # 일치하면 'OK' 버튼을 활성화합니다.
            self.ok_button.setEnabled(True)
        else:
            # 일치하지 않으면 'OK' 버튼을 비활성화합니다.
            self.ok_button.setEnabled(False)


class RebootDialog(QDialog):
    """
    모든 작업이 완료된 후 사용자에게 재부팅을 알리고 카운트다운을 진행하는 대화상자 클래스입니다.
    카운트다운이 0이 되거나 사용자가 '지금 재시작'을 누르면 자동으로 재부팅을 진행합니다.
    """

    def __init__(self, parent=None):
        """RebootDialog 클래스의 생성자입니다."""
        super().__init__(parent)
        self.setWindowTitle("작업 완료")
        self.setModal(True)
        self.resize(350, 150)  # 대화상자의 크기를 적절하게 조절

        # 재부팅까지 남은 시간을 초 단위로 저장하는 변수
        self.countdown = 10

        layout = QVBoxLayout(self)
        # 카운트다운 메시지를 표시할 QLabel 위젯 생성
        self.message_label = QLabel()
        layout.addWidget(self.message_label)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        # 'OK' 버튼의 텍스트를 "지금 재시작"으로 변경합니다.
        self.ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText("지금 재시작")

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # 1초마다 _update_countdown 메서드를 호출할 QTimer를 생성하고 시작합니다.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_countdown)
        self.timer.start(1000)

        # 대화상자가 나타나자마자 첫 카운트다운 메시지를 표시하기 위해 메서드를 한 번 호출합니다.
        self._update_countdown()

    def _update_countdown(self):
        """1초마다 호출되어 카운트다운 숫자를 업데이트하고 0이 되면 자동으로 accept()를 호출하는 슬롯입니다."""
        if self.countdown > 0:
            # 남은 시간이 1초 이상이면 메시지를 업데이트하고 카운트다운 값을 1 감소시킵니다.
            self.message_label.setText(
                f"모든 작업이 완료되었습니다.\n{self.countdown}초 후 시스템을 재시작합니다."
            )
            self.countdown -= 1
        else:
            # 카운트다운이 0이 되면 타이머를 멈추고 accept()를 호출하여 재부팅을 진행합니다.
            self.timer.stop()
            self.accept()

    def accept(self):
        """'지금 재시작' 버튼을 누르거나 카운트다운이 완료되었을 때 호출됩니다."""
        self.timer.stop()  # 혹시 타이머가 실행 중이면 멈춥니다.
        super().accept()  # 부모 클래스의 accept()를 호출하여 대화상자를 닫고 QDialog.Accepted를 반환합니다.

    def reject(self):
        """'취소' 버튼을 눌렀을 때 호출됩니다."""
        self.timer.stop()  # 카운트다운 타이머를 멈춥니다.
        super().reject()  # 부모 클래스의 reject()를 호출하여 대화상자를 닫고 QDialog.Rejected를 반환합니다.
