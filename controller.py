# controller.py

# re 모듈: 정규 표현식을 사용하여 문자열을 처리하는 기능을 제공합니다.
import re

# os 모듈: 운영체제와 상호작용하는 기능을 제공합니다. (예: 파일 경로 다루기, 파일 존재 여부 확인)
import os

# time 모듈: 시간 관련 기능을 제공합니다. (예: 현재 시간 가져오기, 시간 지연)
import time

# sys 모듈: 파이썬 인터프리터와 관련된 변수 및 함수를 제공합니다. (예: 실행 파일 경로 얻기)
import sys

# logging 모듈: 애플리케이션의 이벤트와 오류를 기록하는 로깅 기능을 제공합니다.
import logging

# PyQt6.QtCore 모듈에서 QTimer 클래스를 가져옵니다.
# QTimer: 일정 시간 간격으로 특정 작업을 수행하게 해주는 타이머 클래스입니다.
from PyQt6.QtCore import QTimer

# 각 모듈에서 필요한 클래스들을 가져옵니다.
from view import View  # UI를 담당하는 View 클래스
from models import (
    Options,
    SystemInfo,
)  # 데이터 구조를 정의하는 Options, SystemInfo 데이터 클래스
from loader import Loader  # 시스템 분석을 수행하는 Loader 스레드 클래스
from logger import USER_LOG_LEVEL, log_function_call  # 로깅 관련 상수 및 데코레이터
from dialog import (
    ConfirmationDialog,
    RebootDialog,
)  # 사용자 확인 및 재부팅 대화상자 클래스
from utils import reboot_system  # 시스템 재부팅 유틸리티 함수
from worker import Worker  # 실제 자동화 작업을 수행하는 Worker 스레드 클래스


class Controller:
    """
    애플리케이션의 메인 로직을 담당하는 클래스.
    View(UI)와 Worker/Loader(백그라운드 작업) 사이의 상호작용을 제어합니다.
    MVC(Model-View-Controller) 패턴에서 컨트롤러 역할을 수행합니다.
    """

    def __init__(self, view: View):
        """Controller 클래스의 생성자입니다."""
        self._view = view  # View 객체를 멤버 변수로 저장
        self._loader = Loader()  # 시스템 분석을 위한 Loader 객체 생성
        self._system_info: SystemInfo = (
            None  # 시스템 분석 정보를 저장할 변수, 초기값은 None
        )
        self._worker = None  # 자동화 작업을 위한 Worker 객체를 저장할 변수
        self._descriptions = (
            self._load_descriptions()
        )  # info.txt 파일에서 PC 타입별 설명을 로드
        self._connect_signals()  # UI 이벤트(시그널)와 컨트롤러 메서드(슬롯)를 연결

        # 예상 남은 시간 표시를 위한 타이머 설정
        self._timer = QTimer()  # QTimer 객체 생성
        self._timer.timeout.connect(
            self._update_time_label
        )  # 타이머의 timeout 시그널이 발생할 때마다 _update_time_label 메서드 호출
        self._total_seconds = 0  # 예상되는 총 작업 시간 (초)
        self._start_time = None  # 실제 작업 시작 시간

    def _load_descriptions(self) -> dict:
        """info.txt 파일에서 각 PC 타입에 대한 설명을 읽어와 딕셔너리로 반환합니다."""
        descriptions = {}
        # info.txt의 섹션 이름과 UI의 버튼 ID를 매핑하는 딕셔너리
        key_map = {"내부망": 0, "인터넷": 1, "출장용": 2, "K자회사": 3}

        try:
            # PyInstaller 등으로 패키징되었는지(frozen) 여부를 확인하여 실행 파일의 기본 경로를 결정합니다.
            if getattr(sys, "frozen", False):
                # 패키징된 경우: 실행 파일이 있는 디렉토리
                base_path = os.path.dirname(sys.executable)
            else:
                # 일반 파이썬 스크립트로 실행된 경우: 이 파일(controller.py)이 있는 디렉토리
                base_path = os.path.dirname(os.path.abspath(__file__))

            # info.txt 파일의 전체 경로를 생성합니다.
            info_file_path = os.path.join(base_path, "info.txt")

            # info.txt 파일이 존재하지 않으면 빈 딕셔너리를 반환합니다.
            if not os.path.exists(info_file_path):
                return {}
            # 파일을 utf-8 인코딩으로 읽습니다.
            with open(info_file_path, "r", encoding="utf-8") as f:
                content = f.read()
            # 정규 표현식을 사용하여 "[섹션명]\n내용" 형식의 부분을 모두 찾습니다.
            sections = re.findall(r"\[(.*?)\]\n(.*?)(?=\n\[|$)", content, re.DOTALL)
            for section_name, section_content in sections:
                if section_name in key_map:
                    # key_map을 이용해 섹션 이름을 버튼 ID로 변환하여 딕셔너리에 저장합니다.
                    descriptions[key_map[section_name]] = section_content.strip()
        except Exception as e:
            # 파일 읽기 또는 파싱 중 오류 발생 시 에러 로그를 기록합니다.
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
        # _descriptions 딕셔너리에서 선택된 ID에 해당하는 설명을 가져옵니다. 없으면 default_text를 사용합니다.
        description = self._descriptions.get(type_id, default_text)
        self._view.log_viewer_bottom.setText(description)

    @log_function_call
    def on_loading_finished(self, system_info: SystemInfo):
        """Loader의 시스템 분석이 완료되었을 때 호출되는 메서드."""
        self._system_info = system_info  # 분석된 시스템 정보를 멤버 변수에 저장
        self._view.set_ui_for_loading(False)  # UI를 로딩 완료 상태로 변경

        logging.info(f"분석된 시스템 정보: {system_info}")

        # 데이터 보존이 가능한 환경인지 판단합니다.
        # 조건: 시스템 볼륨이 1개이고, 데이터 볼륨과 부트 볼륨이 모두 존재해야 함.
        is_save_possible = (
            system_info.system_volume_count == 1
            and system_info.data_volume_index != -1
            and system_info.boot_volume_index != -1
        )

        if is_save_possible:
            self._view.set_data_save_enabled(True)  # '데이터 보존' 버튼 활성화
            logging.log(USER_LOG_LEVEL, "분석 완료: 데이터 저장이 가능한 환경입니다.")
        else:
            self._view.set_data_save_enabled(False)  # '데이터 보존' 버튼 비활성화
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
        self._view.set_ui_for_loading(True)  # UI를 로딩 중 상태로 변경
        self._loader.start()  # Loader 스레드 시작

    @log_function_call
    def on_loading_error(self, error_message: str):
        """Loader 스레드에서 오류 발생 시 호출됩니다."""
        logging.log(USER_LOG_LEVEL, f"오류: {error_message}")
        self._view.set_progress_bar_infinite(False)  # 프로그레스 바 무한 모드 해제

    @log_function_call
    def on_start_stop_button_toggled(self, checked: bool):
        """시작/중지 토글 버튼의 상태가 변경될 때 호출됩니다."""
        if checked:  # 버튼이 눌린 상태 (시작)
            # 선택된 PC 타입의 ID를 가져옵니다.
            type_id = self._view.types_button_group.checkedId()
            if type_id == -1:  # 아무것도 선택되지 않았을 경우
                logging.log(USER_LOG_LEVEL, "오류: PC 타입을 먼저 선택해주세요.")
                self._view.start_stop_button.setChecked(
                    False
                )  # 버튼 상태를 다시 '시작'으로 되돌림
                return

            save_checked = self._view.data_save_button.isChecked()
            # '데이터 보존'이 선택되지 않았을 경우 (데이터 삭제)
            if not save_checked:
                dialog = ConfirmationDialog(
                    self._view
                )  # 데이터 삭제 확인 대화상자 표시
                if not dialog.exec():  # 사용자가 '취소'를 누른 경우
                    self._view.start_stop_button.setChecked(False)  # 버튼 상태를 되돌림
                    return

            bitlocker_checked = self._view.bitlocker_button.isChecked()
            # 사용자가 선택한 옵션들을 Options 데이터 클래스에 담습니다.
            user_options = Options(
                type=type_id, save=save_checked, bitlocker=bitlocker_checked
            )
            # View의 start_clicked 시그널을 발생시켜 start_automation 메서드를 호출합니다.
            self._view.start_clicked.emit(user_options)
        else:  # 버튼이 눌리지 않은 상태 (중지)
            # View의 stop_clicked 시그널을 발생시켜 stop_automation 메서드를 호출합니다.
            self._view.stop_clicked.emit()

    @log_function_call
    def start_automation(self, options: Options):
        """자동화 작업(Worker) 스레드를 시작하고 타이머를 설정합니다."""
        self._view.log_viewer_top.clear()  # 상단 로그 뷰어 초기화
        self._on_type_selected(
            self._view.types_button_group.checkedId()
        )  # 하단 설명창 업데이트
        self._view.set_ui_for_task_running(True)  # UI를 작업 실행 중 상태로 변경

        # 예상 작업 시간을 설정합니다.
        # 1. Loader가 이전에 저장된 작업 시간을 읽어왔으면 그 값을 사용합니다.
        if self._system_info.estimated_time_sec > 0:
            self._total_seconds = self._system_info.estimated_time_sec
            logging.info(
                f"저장된 작업 시간({self._total_seconds}초)을 불러와 예상 시간으로 설정합니다."
            )
        # 2. 저장된 시간이 없으면 OS가 설치된 디스크 타입에 따라 기본 시간을 설정합니다.
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

        self._start_time = time.time()  # 실제 작업 시작 시간을 기록
        self._timer.start(1000)  # 1초 간격의 타이머 시작

        # Worker 스레드를 생성하고 시그널을 슬롯에 연결한 후 시작합니다.
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
            self._worker.stop()  # Worker 스레드의 중지 플래그를 설정

    def on_worker_progress_updated(self, value: int):
        """Worker로부터 진행률 업데이트를 받아 UI에 반영합니다."""
        self._view.progress_bar.setValue(value)

    def on_worker_log_updated(self, message: str):
        """Worker로부터 로그 메시지를 받아 UI에 표시합니다."""
        logging.log(USER_LOG_LEVEL, message)

    @log_function_call
    def on_worker_finished(self):
        """Worker 작업이 정상적으로 완료되었을 때 호출됩니다."""
        self._timer.stop()  # 남은 시간 타이머 중지
        self._view.update_time_label("-")  # 남은 시간 라벨 초기화

        elapsed_seconds = self._log_time_gap()  # 실제 소요 시간을 계산하고 로그에 기록
        self._save_completion_time(elapsed_seconds)  # 실제 소요 시간을 파일에 저장

        logging.log(USER_LOG_LEVEL, "모든 작업이 완료되었습니다. 재부팅하시겠습니까?")
        self._view.progress_bar.setValue(100)  # 프로그레스 바를 100%로 설정
        self._view.set_ui_for_task_running(False)  # UI를 작업 완료 상태로 변경
        self._worker = None  # Worker 객체 참조 제거

        # 작업 완료 후 데이터 보존 가능 여부를 다시 판단하여 버튼 상태를 업데이트합니다.
        is_save_possible = (
            self._system_info.system_volume_count == 1
            and self._system_info.data_volume_index != -1
            and self._system_info.boot_volume_index != -1
        )
        if is_save_possible:
            self._view.set_data_save_enabled(True)

        # 재부팅 확인 대화상자를 표시합니다.
        reboot_dialog = RebootDialog(self._view)
        if reboot_dialog.exec():  # 사용자가 '지금 재시작'을 누른 경우
            logging.info("시스템을 재시작합니다.")
            reboot_system()  # 시스템 재부팅 함수 호출
        else:  # 사용자가 '취소'를 누르거나 창을 닫은 경우
            logging.info("재시작이 취소되었습니다.")

    @log_function_call
    def on_worker_error(self, message: str):
        """Worker에서 오류가 발생했을 때 호출됩니다."""
        self._timer.stop()  # 타이머 중지
        self._view.update_time_label("-")  # 남은 시간 라벨 초기화
        self._log_time_gap()  # 오류 발생 시점까지의 소요 시간 기록

        logging.log(USER_LOG_LEVEL, f"오류: {message}")
        self._view.set_ui_for_task_running(False)  # UI를 작업 완료(오류) 상태로 변경
        self._worker = None  # Worker 객체 참조 제거

    def _update_time_label(self):
        """1초마다 호출되어 남은 예상 시간을 계산하고 UI 라벨을 업데이트합니다."""
        if not self._start_time or not self._total_seconds:
            return

        elapsed_seconds = int(time.time() - self._start_time)  # 경과 시간 계산
        remaining_seconds = self._total_seconds - elapsed_seconds  # 남은 시간 계산

        if remaining_seconds < 0:
            remaining_seconds = 0

        # 남은 시간을 분과 초로 변환합니다.
        minutes, seconds = divmod(remaining_seconds, 60)
        # "MM:SS" 형식의 문자열로 만듭니다.
        time_str = f"{minutes:02d}:{seconds:02d}"
        self._view.update_time_label(time_str)  # UI 라벨 업데이트

    def _log_time_gap(self) -> int:
        """
        예상 시간과 실제 소요 시간의 차이를 계산하여 로그에 기록하고,
        실제 소요된 시간을 초 단위로 반환합니다.
        """
        if not self._start_time:
            return 0

        elapsed_seconds = int(time.time() - self._start_time)  # 실제 소요 시간

        if self._total_seconds > 0:
            gap_seconds = (
                self._total_seconds - elapsed_seconds
            )  # 예상 시간과 실제 시간의 차이

            set_time_str = f"{self._total_seconds // 60}분 {self._total_seconds % 60}초"
            elapsed_time_str = f"{elapsed_seconds // 60}분 {elapsed_seconds % 60}초"

            gap_abs_seconds = abs(gap_seconds)
            gap_str = f"{gap_abs_seconds // 60}분 {gap_abs_seconds % 60}초"

            if gap_seconds >= 0:
                gap_summary = f"{gap_str} 빠름"  # 실제가 예상보다 빠름
            else:
                gap_summary = f"{gap_str} 느림"  # 실제가 예상보다 느림

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

        # 저장할 파일의 전체 경로를 생성합니다.
        time_file_path = os.path.join(
            self._system_info.driver_path, "completion_time.txt"
        )
        try:
            # 파일을 쓰기 모드로 열어 실제 소요 시간을 초 단위로 기록합니다.
            with open(time_file_path, "w") as f:
                f.write(str(elapsed_seconds))
            logging.info(
                f"작업 소요 시간({elapsed_seconds}초)을 '{time_file_path}'에 저장했습니다."
            )
        except IOError as e:
            # 파일 쓰기 중 오류 발생 시 에러 로그를 기록합니다.
            logging.error(f"작업 시간을 파일에 쓰는 중 오류가 발생했습니다: {e}")
