# view.py
import os

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QTextEdit, QProgressBar, QMessageBox, QDialog, QTextBrowser)
from PyQt5.QtCore import QThread, QSize
from functools import partial

# --- [파일 분리] ---
from worker import Worker
from dialog import SelectDataPartitionDialog


class View(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Kdic Setup V 1.3')
        self.setGeometry(100, 100, 640, 480)
        self.setWindowIcon(QIcon(r'icon\kdic.ico'))

        main_layout = QVBoxLayout()

        self.text_widget = QTextEdit(self)
        self.text_widget.setReadOnly(True)
        self.text_widget.setStyleSheet("border: 1px solid black;")
        self.text_widget.setFixedHeight(200)
        main_layout.addWidget(self.text_widget)

        self.info_browser = QTextBrowser(self)
        self.info_browser.setReadOnly(True)
        self.info_browser.setStyleSheet("border: 1px solid black;")
        self.info_browser.setFixedHeight(80)
        main_layout.addWidget(self.info_browser)

        button_layout = QVBoxLayout()

        self.mode_buttons_dict = {}
        self.data_buttons_dict = {}

        self.mode_names = ["업무용", "인터넷용", "출장용", "K자회사"]
        data_names = ["데이터 보존", "데이터 삭제"]

        grid_rows = [QHBoxLayout(), QHBoxLayout()]
        for i, name in enumerate(self.mode_names):
            btn = QPushButton(name, self)
            btn.setCheckable(True)
            self.mode_buttons_dict[name] = btn
            grid_rows[i // 2].addWidget(btn)

        button_layout.addLayout(grid_rows[0])
        button_layout.addLayout(grid_rows[1])

        data_row = QHBoxLayout()
        for name in data_names:
            btn = QPushButton(name, self)
            btn.setCheckable(True)
            self.data_buttons_dict[name] = btn
            data_row.addWidget(btn)
        button_layout.addLayout(data_row)

        main_layout.addLayout(button_layout)

        self.start_button = QPushButton("시작", self)
        main_layout.addWidget(self.start_button)

        self.progress_bar = QProgressBar(self)
        main_layout.addWidget(self.progress_bar)

        self.setLayout(main_layout)

        self.worker = None
        self.loading_thread = None

        self.init_ui()

    def init_ui(self):
        self.start_button.setEnabled(False)
        for btn in self.data_buttons_dict.values():
            btn.setEnabled(False)

        mode_button_group = list(self.mode_buttons_dict.values())
        for btn in mode_button_group:
            btn.clicked.connect(partial(self.on_button_group_clicked, mode_button_group, btn))

        data_button_group = list(self.data_buttons_dict.values())
        for btn in data_button_group:
            btn.clicked.connect(partial(self.on_button_group_clicked, data_button_group, btn))

        self.start_button.clicked.connect(self.start_stop_worker)
        self.update_info()
        self.start_worker()

    def on_button_group_clicked(self, button_group, clicked_button):
        for btn in button_group:
            btn.setChecked(btn == clicked_button)
        if clicked_button in self.mode_buttons_dict.values():
            self.update_info()

    def enable_buttons(self, exist_folders):
        self.start_button.setEnabled(True)
        for btn in self.data_buttons_dict.values():
            btn.setEnabled(exist_folders)
            btn.setCheckable(True)

        if exist_folders:
            self.data_buttons_dict["데이터 보존"].setChecked(True)

    def start_stop_worker(self):
        if self.start_button.text() == "시작":
            if not any(btn.isChecked() for btn in self.mode_buttons_dict.values()):
                QMessageBox.warning(self, "경고", "용도 선택은 필수 사항입니다.")
                return

            preserve_btn = self.data_buttons_dict["데이터 보존"]
            delete_btn = self.data_buttons_dict["데이터 삭제"]

            if not preserve_btn.isEnabled() or delete_btn.isChecked():
                if QMessageBox.warning(
                        self, "경고", "모든 데이터가 삭제 됩니다. 그래도 진행하시겠습니까?",
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                ) == QMessageBox.No:
                    return
            self.run_setup()
        else:
            self.stop_worker()

    def start_worker(self):
        self.worker = Worker()
        self.worker.log_signal.connect(self.update_log)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.data_signal.connect(self.enable_buttons)
        self.worker.multiple_data_partitions_signal.connect(self.handle_multiple_data_partitions)

        self.loading_thread = QThread()
        self.worker.moveToThread(self.loading_thread)
        self.loading_thread.started.connect(self.worker.load)
        self.worker.load_finished_signal.connect(self.on_load_finished)
        self.loading_thread.start()

        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(0)

    def handle_multiple_data_partitions(self, partitions):
        """여러 데이터 파티션이 감지되었을 때 선택 다이얼로그를 띄웁니다."""
        dialog = SelectDataPartitionDialog(partitions, self)
        if dialog.exec_() == QDialog.Accepted:
            selected_volume = dialog.selected_partition
            if selected_volume:
                self.worker.set_selected_data_volume(selected_volume)
        else:
            self.log_signal.emit("파티션 선택이 취소되었습니다. 데이터 보존이 불가능합니다.")
            self.data_signal.emit(False)

    def on_load_finished(self):
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.loading_thread.quit()
        self.loading_thread.wait()
        self.start_button.setEnabled(True)

    def run_setup(self):
        self.start_button.setText("중지")
        self.toggle_buttons_enabled(False)

        for name, btn in self.mode_buttons_dict.items():
            if btn.isChecked():
                self.worker.path = self.mode_names.index(name)
                break

        preserve_btn = self.data_buttons_dict["데이터 보존"]
        self.worker.save = preserve_btn.isEnabled() and preserve_btn.isChecked()
        self.worker.start()

    def stop_worker(self):
        if self.worker:
            self.worker.stop()

        all_buttons = list(self.mode_buttons_dict.values()) + list(self.data_buttons_dict.values())
        for btn in all_buttons:
            btn.setChecked(False)

        self.toggle_buttons_enabled(True)
        self.start_button.setText("시작")
        self.progress_bar.setValue(0)
        self.text_widget.clear()

        self.init_ui()

    def toggle_buttons_enabled(self, state):
        all_buttons = list(self.mode_buttons_dict.values()) + list(self.data_buttons_dict.values())
        for btn in all_buttons:
            if not btn.isChecked():
                btn.setEnabled(state)

    def _parse_info_file(self):
        """info.txt 파일을 파싱하여 self.info_content 딕셔너리에 저장합니다."""
        self.info_content = {}
        info_file_path = r"..\wim\info.txt"

        try:
            with open(info_file_path, "r", encoding="utf-8") as f:
                current_key = None
                content_buffer = []
                for line in f:
                    stripped_line = line.strip()
                    if stripped_line.startswith('[') and stripped_line.endswith(']'):
                        if current_key and content_buffer:
                            self.info_content[current_key] = '\n'.join(content_buffer).strip()
                        current_key = stripped_line[1:-1]
                        content_buffer = []
                    elif current_key:
                        content_buffer.append(line.strip())  # 불필요한 공백 제거

                # 파일의 마지막 섹션 저장
                if current_key and content_buffer:
                    self.info_content[current_key] = '\n'.join(content_buffer).strip()

        except FileNotFoundError:
            self.info_browser.setText(f"설명 파일을 찾을 수 없습니다.\n경로: {os.path.abspath(info_file_path)}")
        except Exception as e:
            self.info_browser.setText(f"설명 파일 로딩 중 오류 발생:\n{e}")

    def update_info(self):
        """선택된 용도에 따라 설명창의 내용을 업데이트합니다."""

        self._parse_info_file()
        selected_mode = None
        for mode, btn in self.mode_buttons_dict.items():
            if btn.isChecked():
                selected_mode = mode
                break

        if selected_mode:
            # 파싱된 딕셔너리에서 내용 가져오기
            info_text = self.info_content.get(selected_mode, f"'{selected_mode}'에 대한 설명을 찾을 수 없습니다.")
            self.info_browser.setText(info_text)
        else:
            # 아무것도 선택되지 않았을 때
            self.info_browser.setText("용도 선택은 필수입니다.")

    def update_log(self, log_message):
        self.text_widget.append(log_message)

    def update_progress(self, value):
        self.progress_bar.setValue(value)
