# controller.py 전체 코드

import logging
import re
import os
import time
from PyQt6.QtCore import QTimer
from view import View
from models import Options, SystemInfo
from loader import Loader
from logger import USER_LOG_LEVEL, log_function_call
from dialog import ConfirmationDialog, RebootDialog
from utils import reboot_system
from worker import Worker


class Controller:
    def __init__(self, view: View):
        self._view = view
        self._loader = Loader()
        self._system_info: SystemInfo = None
        self._worker = None
        self._descriptions = self._load_descriptions()
        self._connect_signals()

        self._timer = QTimer()
        self._timer.timeout.connect(self._update_time_label)
        self._total_seconds = 0
        self._start_time = None

    def _load_descriptions(self) -> dict:
        descriptions = {}
        key_map = {"내부망": 0, "인터넷": 1, "출장용": 2, "K자회사": 3}
        try:
            info_file_path = os.path.join(os.getcwd(), "info.txt")
            if not os.path.exists(info_file_path):
                return {}
            with open(info_file_path, "r", encoding="utf-8") as f:
                content = f.read()
            sections = re.findall(r"\[(.*?)\]\n(.*?)(?=\n\[|$)", content, re.DOTALL)
            for section_name, section_content in sections:
                if section_name in key_map:
                    descriptions[key_map[section_name]] = section_content.strip()
        except Exception as e:
            logging.error(f"info.txt 파일을 읽거나 파싱하는 데 실패했습니다: {e}")
        return descriptions

    def _connect_signals(self):
        self._view.start_clicked.connect(self.start_automation)
        self._view.stop_clicked.connect(self.stop_automation)
        self._view.start_stop_button.clicked.connect(self.on_start_stop_button_toggled)
        self._loader.finished.connect(self.on_loading_finished)
        self._loader.error_occurred.connect(self.on_loading_error)
        self._view.types_button_group.idClicked.connect(self._on_type_selected)

    def _on_type_selected(self, type_id: int):
        default_text = "타입을 선택하면 여기에 설명이 표시됩니다."
        description = self._descriptions.get(type_id, default_text)
        self._view.log_viewer_bottom.setText(description)

    @log_function_call
    def on_loading_finished(self, system_info: SystemInfo):
        self._system_info = system_info
        self._view.set_ui_for_loading(False)

        logging.info(f"분석된 시스템 정보: {system_info}")
        self._view.log_viewer_bottom.setPlaceholderText(
            "타입을 선택하면 여기에 설명이 표시됩니다."
        )

        is_save_possible = (
            system_info.system_volume_count == 1
            and system_info.data_volume_index != -1
            and system_info.boot_volume_index != -1
        )

        if is_save_possible:
            self._view.set_data_save_enabled(True)
            logging.log(USER_LOG_LEVEL, "분석 완료: 데이터 저장이 가능한 환경입니다.")
        else:
            self._view.set_data_save_enabled(False)
            if system_info.system_volume_count > 1:
                logging.log(
                    USER_LOG_LEVEL,
                    "분석 완료: 시스템 볼륨이 2개 이상 발견되어 데이터 저장이 불가능합니다.",
                )
            else:
                logging.log(
                    USER_LOG_LEVEL, "분석 완료: 데이터 저장이 불가능한 환경입니다."
                )

    @log_function_call
    def start_loading(self):
        self._view.set_ui_for_loading(True)
        self._loader.start()

    @log_function_call
    def on_loading_error(self, error_message: str):
        logging.log(USER_LOG_LEVEL, f"오류: {error_message}")
        self._view.set_progress_bar_infinite(False)

    @log_function_call
    def on_start_stop_button_toggled(self, checked):
        if checked:
            type_id = self._view.types_button_group.checkedId()
            if type_id == -1:
                logging.log(USER_LOG_LEVEL, "오류: PC 타입을 먼저 선택해주세요.")
                self._view.start_stop_button.setChecked(False)
                return

            save_checked = self._view.data_save_button.isChecked()

            if not save_checked:
                dialog = ConfirmationDialog(self._view)
                if not dialog.exec():
                    self._view.start_stop_button.setChecked(False)
                    return

            bitlocker_checked = self._view.bitlocker_button.isChecked()
            user_options = Options(
                type=type_id, save=save_checked, bitlocker=bitlocker_checked
            )
            self._view.start_clicked.emit(user_options)
        else:
            self._view.stop_clicked.emit()

    @log_function_call
    def start_automation(self, options: Options):
        self._view.log_viewer_top.clear()
        self._view.set_ui_for_task_running(True)

        disk_type = self._system_info.system_disk_type.upper()
        if "NVME" in disk_type:
            self._total_seconds = 6 * 60
        elif "SSD" in disk_type:
            self._total_seconds = 7 * 60
        else:
            self._total_seconds = 8 * 60

        self._start_time = time.time()
        self._timer.start(1000)

        self._worker = Worker(options, self._system_info)
        self._worker.progress_updated.connect(self.on_worker_progress_updated)
        self._worker.log_updated.connect(self.on_worker_log_updated)
        self._worker.finished.connect(self.on_worker_finished)
        self._worker.error_occurred.connect(self.on_worker_error)
        self._worker.start()

    @log_function_call
    def stop_automation(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()

    def on_worker_progress_updated(self, value: int):
        self._view.progress_bar.setValue(value)

    def on_worker_log_updated(self, message: str):
        logging.log(USER_LOG_LEVEL, message)

    @log_function_call
    def on_worker_finished(self):
        self._timer.stop()
        self._view.update_time_label("-")

        self._log_time_gap()

        logging.log(USER_LOG_LEVEL, "모든 작업이 완료되었습니다. 재부팅하시겠습니까?")
        self._view.progress_bar.setValue(100)
        self._view.set_ui_for_task_running(False)
        self._worker = None

        is_save_possible = (
            self._system_info.system_volume_count == 1
            and self._system_info.data_volume_index != -1
            and self._system_info.boot_volume_index != -1
        )
        if is_save_possible:
            self._view.set_data_save_enabled(True)

        reboot_dialog = RebootDialog(self._view)
        if reboot_dialog.exec():
            logging.info("시스템을 재시작합니다.")
            reboot_system()
        else:
            logging.info("재시작이 취소되었습니다.")

    @log_function_call
    def on_worker_error(self, message: str):
        self._timer.stop()
        self._view.update_time_label("-")

        self._log_time_gap()

        logging.log(USER_LOG_LEVEL, f"오류: {message}")
        self._view.set_ui_for_task_running(False)
        self._worker = None

    def _update_time_label(self):
        if not self._start_time or not self._total_seconds:
            return

        elapsed_seconds = int(time.time() - self._start_time)
        remaining_seconds = self._total_seconds - elapsed_seconds

        if remaining_seconds < 0:
            remaining_seconds = 0

        minutes, seconds = divmod(remaining_seconds, 60)
        time_str = f"{minutes:02d}:{seconds:02d}"
        self._view.update_time_label(time_str)

    def _log_time_gap(self):
        """설정 시간과 실제 소요 시간의 차이를 계산하여 로그에 기록합니다."""
        if not self._start_time or not self._total_seconds:
            return

        elapsed_seconds = int(time.time() - self._start_time)
        gap_seconds = self._total_seconds - elapsed_seconds

        set_time_str = f"{self._total_seconds // 60}분 {self._total_seconds % 60}초"
        elapsed_time_str = f"{elapsed_seconds // 60}분 {elapsed_seconds % 60}초"

        gap_abs_seconds = abs(gap_seconds)
        gap_str = f"{gap_abs_seconds // 60}분 {gap_abs_seconds % 60}초"

        if gap_seconds >= 0:
            gap_summary = f"{gap_str} 빠름"
        else:
            gap_summary = f"{gap_str} 느림"

        log_message = f"시간 분석: 설정({set_time_str}) - 실제({elapsed_time_str}) = {gap_summary}"
        logging.info(log_message)
