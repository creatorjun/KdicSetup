# view.py

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QGridLayout,
    QGroupBox,
    QPushButton,
    QProgressBar,
    QButtonGroup,
    QLabel,
)
from logger import QtLogHandler


class View(QMainWindow):
    start_clicked = pyqtSignal(object)
    stop_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kdic Setup v. 2.0")
        self._set_window_size_and_position(640, 480)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.log_viewer_top = self._create_log_viewer(
            "시스템 분석중입니다. 잠시만 기다려주세요."
        )
        # 초기 안내 문구를 여기서 한 번만 설정하도록 수정
        self.log_viewer_bottom = self._create_log_viewer(
            "타입을 선택하면 여기에 설명이 표시됩니다."
        )
        self.types_group = self._create_types_group()
        bottom_layout = self._create_bottom_layout()

        main_layout.addWidget(self.log_viewer_top, 2)
        main_layout.addWidget(self.log_viewer_bottom, 1)
        main_layout.addWidget(self.types_group)
        main_layout.addLayout(bottom_layout)

        self.types_button_group.buttonClicked.connect(
            self._update_bitlocker_button_state
        )
        self.log_handler = QtLogHandler()
        self.log_handler.log_received.connect(self.log_viewer_top.append)

    def _set_window_size_and_position(self, width: int, height: int):
        self.resize(width, height)
        screen = QApplication.primaryScreen()
        if screen:
            center_point = screen.geometry().center()
            self.move(center_point.x() - width // 2, center_point.y() - height // 2)

    def _create_log_viewer(self, placeholder: str) -> QTextEdit:
        log_viewer = QTextEdit()
        log_viewer.setReadOnly(True)
        log_viewer.setPlaceholderText(placeholder)
        return log_viewer

    def _create_types_group(self) -> QGroupBox:
        group_box = QGroupBox("타입 선택")
        grid_layout = QGridLayout(group_box)
        buttons = {0: "내부망", 1: "인터넷", 2: "출장용", 3: "K자회사"}
        self.types_button_group = QButtonGroup(self)
        self.types_button_group.setExclusive(True)

        for i, text in buttons.items():
            button = QPushButton(text)
            button.setCheckable(True)
            self.types_button_group.addButton(button, i)
            row, col = divmod(i, 2)
            grid_layout.addWidget(button, row, col)

        return group_box

    def _create_bottom_layout(self) -> QVBoxLayout:
        bottom_layout = QVBoxLayout()

        self.data_save_button = QPushButton("데이터 보존")
        self.data_save_button.setCheckable(True)
        self.data_save_button.setEnabled(False)

        self.bitlocker_button = QPushButton("BitLocker 설정")
        self.bitlocker_button.setCheckable(True)
        self.bitlocker_button.setEnabled(False)

        self.start_stop_button = QPushButton("시작")
        self.start_stop_button.setCheckable(True)
        self.start_stop_button.setEnabled(False)

        bottom_layout.addWidget(self.data_save_button)
        bottom_layout.addWidget(self.bitlocker_button)
        bottom_layout.addWidget(self.start_stop_button)

        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.time_label = QLabel("예상 남은 시간: -")
        self.time_label.setFixedWidth(150)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.time_label)
        bottom_layout.addLayout(progress_layout)

        return bottom_layout

    def set_data_save_enabled(self, enabled: bool):
        self.data_save_button.setEnabled(enabled)
        self.data_save_button.setChecked(enabled)

    def _update_bitlocker_button_state(self):
        is_trip_options = self.types_button_group.checkedId() == 2
        self.bitlocker_button.setEnabled(is_trip_options)
        self.bitlocker_button.setChecked(is_trip_options)

    def set_ui_for_loading(self, is_loading: bool):
        interactive = not is_loading
        self.types_group.setEnabled(interactive)
        self.start_stop_button.setEnabled(interactive)
        self.data_save_button.setEnabled(False)
        self.data_save_button.setChecked(False)
        if not is_loading:
            self._update_bitlocker_button_state()
        else:
            self.bitlocker_button.setEnabled(False)
            self.bitlocker_button.setChecked(False)
        self.set_progress_bar_infinite(is_loading)

    def set_ui_for_task_running(self, is_running: bool):
        interactive = not is_running
        self.types_group.setEnabled(interactive)
        self.data_save_button.setEnabled(interactive)
        self.bitlocker_button.setEnabled(interactive)
        if not is_running:
            self._update_bitlocker_button_state()
            self.data_save_button.setEnabled(False)
            self.data_save_button.setChecked(False)
        self.start_stop_button.setText("중지" if is_running else "시작")
        self.start_stop_button.setChecked(is_running)

    def set_progress_bar_infinite(self, active: bool):
        if active:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)

    def update_time_label(self, time_str: str):
        """(Controller용) 예상 남은 시간 라벨을 업데이트합니다."""
        self.time_label.setText(f"예상 남은 시간: {time_str}")
