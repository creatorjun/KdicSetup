# controller.py

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
    """
    애플리ケーション의 메인 로직을 담당하는 클래스.
    View(UI)와 Worker/Loader(백그라운드 작업) 사이의 상호작용을 제어합니다.
    """

    def __init__(self, view: View):
        self._view = view
        self._loader = Loader()
        self._system_info: SystemInfo = None
        self._worker = None
        self._descriptions = self._load_descriptions()  # PC 타입별 설명 로드
        self._connect_signals()  # UI 이벤트와 컨트롤러 메서드 연결

        # 예상 남은 시간 표시를 위한 타이머 설정
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_time_label)
        self._total_seconds = 0  # 예상되는 총 작업 시간 (초)
        self._start_time = None  # 실제 작업 시작 시간

    def _load_descriptions(self) -> dict:
        """info.txt 파일에서 각 PC 타입에 대한 설명을 읽어와 딕셔너리로 반환합니다."""
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
        """UI 요소의 시그널(이벤트)을 해당 컨트롤러 메서드(슬롯)에 연결합니다."""
        self._view.start_clicked.connect(self.start_automation)
        self._view.stop_clicked.connect(self.stop_automation)
        self._view.start_stop_button.clicked.connect(self.on_start_stop_button_toggled)
        self._loader.finished.connect(self.on_loading_finished)
        self._loader.error_occurred.connect(self.on_loading_error)
        self._view.types_button_group.idClicked.connect(self._on_type_selected)

    def _on_type_selected(self, type_id: int):
        """PC 타입 라디오 버튼이 선택되었을 때, 하단 설명란에 해당 타입의 설명을 표시합니다."""
        default_text = "타입을 선택하면 여기에 설명이 표시됩니다."
        description = self._descriptions.get(type_id, default_text)
        self._view.log_viewer_bottom.setText(description)

    @log_function_call
    def on_loading_finished(self, system_info: SystemInfo):
        """Loader의 시스템 분석이 완료되었을 때 호출되는 메서드."""
        self._system_info = system_info
        self._view.set_ui_for_loading(False)  # 로딩 상태 UI 해제

        logging.info(f"분석된 시스템 정보: {system_info}")
        self._view.log_viewer_bottom.setPlaceholderText(
            "타입을 선택하면 여기에 설명이 표시됩니다."
        )

        # 데이터 보존이 가능한 환경인지 판단
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
        """프로그램 시작 시 시스템 분석(Loader) 스레드를 시작합니다."""
        self._view.set_ui_for_loading(True)
        self._loader.start()

    @log_function_call
    def on_loading_error(self, error_message: str):
        """Loader 스레드에서 오류 발생 시 호출됩니다."""
        logging.log(USER_LOG_LEVEL, f"오류: {error_message}")
        self._view.set_progress_bar_infinite(False)

    @log_function_call
    def on_start_stop_button_toggled(self, checked: bool):
        """시작/중지 토글 버튼의 상태가 변경될 때 호출됩니다."""
        if checked:  # 시작 버튼을 눌렀을 때
            type_id = self._view.types_button_group.checkedId()
            if type_id == -1:
                logging.log(USER_LOG_LEVEL, "오류: PC 타입을 먼저 선택해주세요.")
                self._view.start_stop_button.setChecked(False)
                return

            save_checked = self._view.data_save_button.isChecked()
            # 데이터 삭제 옵션 선택 시 확인 대화상자 표시
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
        else:  # 중지 버튼을 눌렀을 때
            self._view.stop_clicked.emit()

    @log_function_call
    def start_automation(self, options: Options):
        """자동화 작업(Worker) 스레드를 시작하고 타이머를 설정합니다."""
        # 상단 로그창만 비우고, 하단 설명창은 그대로 둡니다.
        self._view.log_viewer_top.clear()
        self._view.set_ui_for_task_running(True)

        # 1. Loader가 읽어온 예상 시간이 있으면 그 값을 사용
        if self._system_info.estimated_time_sec > 0:
            self._total_seconds = self._system_info.estimated_time_sec
            logging.info(
                f"저장된 작업 시간({self._total_seconds}초)을 불러와 예상 시간으로 설정합니다."
            )
        # 2. 저장된 시간이 없으면 디스크 타입에 따라 기본 예상 시간 설정
        else:
            disk_type = self._system_info.system_disk_type.upper()
            if "NVME" in disk_type:
                self._total_seconds = 6 * 60  # NVMe: 6분
            elif "SSD" in disk_type:
                self._total_seconds = 7 * 60  # SSD: 7분
            else:
                self._total_seconds = 8 * 60  # HDD: 8분
            logging.info(
                f"{disk_type} 디스크 타입에 따라 예상 시간을 {self._total_seconds}초로 설정합니다."
            )

        self._start_time = time.time()
        self._timer.start(1000)

        # Worker 스레드 생성 및 시그널 연결 후 시작
        self._worker = Worker(options, self._system_info)
        self._worker.progress_updated.connect(self.on_worker_progress_updated)
        self._worker.log_updated.connect(self.on_worker_log_updated)
        self._worker.finished.connect(self.on_worker_finished)
        self._worker.error_occurred.connect(self.on_worker_error)
        self._worker.start()

    @log_function_call
    def stop_automation(self):
        """Worker 스레드를 중단시킵니다."""
        if self._worker and self._worker.isRunning():
            self._worker.stop()

    def on_worker_progress_updated(self, value: int):
        """Worker로부터 진행률 업데이트를 받아 UI에 반영합니다."""
        self._view.progress_bar.setValue(value)

    def on_worker_log_updated(self, message: str):
        """Worker로부터 로그 메시지를 받아 UI에 표시합니다."""
        logging.log(USER_LOG_LEVEL, message)

    @log_function_call
    def on_worker_finished(self):
        """Worker 작업이 정상적으로 완료되었을 때 호출됩니다."""
        self._timer.stop()
        self._view.update_time_label("-")

        elapsed_seconds = self._log_time_gap()
        self._save_completion_time(elapsed_seconds)  # 실제 소요 시간을 파일에 저장

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

        # 재부팅 확인 대화상자 표시
        reboot_dialog = RebootDialog(self._view)
        if reboot_dialog.exec():
            logging.info("시스템을 재시작합니다.")
            reboot_system()
        else:
            logging.info("재시작이 취소되었습니다.")

    @log_function_call
    def on_worker_error(self, message: str):
        """Worker에서 오류가 발생했을 때 호출됩니다."""
        self._timer.stop()
        self._view.update_time_label("-")
        self._log_time_gap()

        logging.log(USER_LOG_LEVEL, f"오류: {message}")
        self._view.set_ui_for_task_running(False)
        self._worker = None

    def _update_time_label(self):
        """1초마다 호출되어 남은 예상 시간을 계산하고 UI 라벨을 업데이트합니다."""
        if not self._start_time or not self._total_seconds:
            return

        elapsed_seconds = int(time.time() - self._start_time)
        remaining_seconds = self._total_seconds - elapsed_seconds

        if remaining_seconds < 0:
            remaining_seconds = 0

        minutes, seconds = divmod(remaining_seconds, 60)
        time_str = f"{minutes:02d}:{seconds:02d}"
        self._view.update_time_label(time_str)

    def _log_time_gap(self) -> int:
        """
        예상 시간과 실제 소요 시간의 차이를 계산하여 로그에 기록하고,
        실제 소요된 시간을 초 단위로 반환합니다.
        """
        if not self._start_time:
            return 0

        elapsed_seconds = int(time.time() - self._start_time)

        if self._total_seconds > 0:
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

        return elapsed_seconds

    def _save_completion_time(self, elapsed_seconds: int):
        """
        실제 작업 소요 시간을 드라이버 경로 안의 'completion_time.txt' 파일에 기록합니다.
        이 파일은 다음 실행 시 예상 시간을 불러오는 데 사용됩니다.
        """
        if not self._system_info or not self._system_info.driver_path:
            logging.warning(
                "드라이버 경로를 찾을 수 없어 작업 시간을 저장할 수 없습니다."
            )
            return

        time_file_path = os.path.join(
            self._system_info.driver_path, "completion_time.txt"
        )
        try:
            with open(time_file_path, "w") as f:
                f.write(str(elapsed_seconds))
            logging.info(
                f"작업 소요 시간({elapsed_seconds}초)을 '{time_file_path}'에 저장했습니다."
            )
        except IOError as e:
            logging.error(f"작업 시간을 파일에 쓰는 중 오류가 발생했습니다: {e}")
