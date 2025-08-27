# worker.py

# os 모듈: 운영체제와 상호작용하는 기능을 제공합니다. (파일 경로, 파일 존재 여부 확인 등)
import os

# re 모듈: 정규 표현식을 사용하여 문자열 검색, 파싱 등의 작업을 수행합니다.
import re

# shutil 모듈: 파일 및 디렉토리 복사, 이동, 삭제 등 고수준 파일 연산을 제공합니다.
import shutil

# logging 모듈: 이벤트 기록(로깅)을 위한 표준 라이브러리입니다.
import logging

# typing 모듈: 타입 힌트를 제공하여 코드의 가독성과 안정성을 높입니다.
from typing import List

# PyQt6.QtCore 모듈: Qt의 핵심 비-GUI 기능을 포함합니다.
# QThread: GUI의 반응성을 유지하기 위해 시간이 오래 걸리는 작업을 별도의 스레드에서 실행하게 해주는 클래스입니다.
# pyqtSignal: 스레드 간 안전한 통신을 위한 사용자 정의 시그널을 생성합니다.
from PyQt6.QtCore import QThread, pyqtSignal

# utils.py 모듈: 프로그램 전반에서 사용되는 유틸리티 함수들을 포함합니다.
import utils

# models.py 모듈: Options, SystemInfo 등 프로그램에서 사용하는 데이터 구조를 정의합니다.
from models import Options, SystemInfo


class UserCancelledError(Exception):
    """사용자가 작업을 중단했을 때 발생하는 사용자 정의 예외 클래스입니다."""

    pass


class Worker(QThread):
    """
    실제 PC 초기화 자동화 작업을 수행하는 스레드 클래스입니다.
    포맷, 이미지 적용, 드라이버 설치 등 시간이 오래 걸리는 작업을 담당하여
    메인 UI 스레드가 멈추지 않도록 합니다.
    """

    # pyqtSignal(int): 작업 진행률(0-100)을 Controller로 전달하는 시그널
    progress_updated = pyqtSignal(int)
    # pyqtSignal(str): 작업 중 발생하는 로그 메시지를 Controller로 전달하는 시그널
    log_updated = pyqtSignal(str)
    # pyqtSignal(): 모든 작업이 성공적으로 완료되었음을 Controller에 알리는 시그널
    finished = pyqtSignal()
    # pyqtSignal(str): 작업 중 오류가 발생했음을 오류 메시지와 함께 Controller에 알리는 시그널
    error_occurred = pyqtSignal(str)

    def __init__(self, options: Options, system_info: SystemInfo):
        """Worker 클래스의 생성자입니다."""
        # 부모 클래스인 QThread의 생성자를 호출합니다.
        super().__init__()
        # 사용자가 선택한 옵션(PC 타입, 데이터 보존 여부 등)을 저장합니다.
        self._options = options
        # Loader가 분석한 시스템 정보를 저장합니다.
        self._system_info = system_info
        # 스레드의 실행 상태를 제어하는 플래그입니다. False가 되면 스레드가 작업을 중단합니다.
        self._is_running = True
        # 현재까지의 누적 진행률을 저장하는 변수입니다.
        self.current_progress = 0

    def run(self):
        """
        QThread.start()가 호출될 때 실행되는 스레드의 메인 메서드입니다.
        자동화 작업의 전체 흐름(오케스트레이션)을 제어합니다.
        """
        try:
            # 옵션의 type ID를 실제 PC 타입 문자열로 변환하는 딕셔너리
            type_map = {
                0: "업무용",
                1: "인터넷용",
                2: "출장용",
                3: "K자회사",
                4: "업무용",  # ID 4는 예비 또는 호환성을 위해 추가되었을 수 있음
            }
            pc_type_str = type_map.get(self._options.type, "알 수 없음")
            save_str = "보존" if self._options.save else "삭제"

            # 작업 시작을 알리는 로그 메시지를 생성하고 UI에 전달합니다.
            start_message = (
                f"데이터를 {save_str}하고 '{pc_type_str}'(으)로 초기화합니다."
            )
            self.log_updated.emit(start_message)

            # --- 작업 단계별 메서드 호출 ---
            # 1. OS 설치 및 부팅에 필요한 드라이브 문자(C:, D:, Z:)를 설정합니다.
            self._setup_letters()
            self._update_progress(1)  # 진행률 1% 증가
            # 2. '데이터 보존' 여부에 따라 디스크를 포맷하고 파티션을 생성합니다.
            self._format()
            self._update_progress(1)  # 진행률 1% 증가

            # 3. WIM 이미지 파일을 OS 파티션(C:)에 적용합니다. 전체 작업의 75%를 차지합니다.
            apply_task_weight = 75
            self._apply_image(
                start_progress=self.current_progress, task_weight=apply_task_weight
            )
            self.current_progress += (
                apply_task_weight  # 이미지 적용 후 진행률을 한번에 더함
            )

            driver_path = self._system_info.driver_path

            # 4. 시스템에 맞는 드라이버를 설치합니다. 전체 작업의 13%를 차지합니다.
            driver_task_weight = 13
            self._install_drivers_with_dism(
                driver_path,
                start_progress=self.current_progress,
                task_weight=driver_task_weight,
            )
            self.current_progress += (
                driver_task_weight  # 드라이버 설치 후 진행률을 한번에 더함
            )

            # 5. 사용자 폴더, 시작 메뉴 레이아웃 등 기타 파일들을 복원합니다.
            self._restore()

            # 6. 시스템이 부팅될 수 있도록 부팅 정보를 구성합니다.
            self._configure_boot()
            self._update_progress(1)  # 진행률 1% 증가

            # 모든 작업이 끝나면 진행률을 100%로 설정하고 완료 신호를 보냅니다.
            self.progress_updated.emit(100)
            self.finished.emit()

        except UserCancelledError:
            # 사용자가 '중지' 버튼을 눌러 작업을 취소한 경우, 아무것도 하지 않고 스레드를 종료합니다.
            pass
        except Exception as e:
            # 예상치 못한 다른 예외가 발생한 경우, 예외를 로깅하고 오류 신호를 보냅니다.
            logging.exception("Worker.run에서 처리되지 않은 예외 발생")
            self.error_occurred.emit(f"작업 중 오류 발생: {e}")

    def _update_progress(self, value: int):
        """현재 진행률에 주어진 값을 더하고 UI를 업데이트합니다."""
        self.current_progress += value
        self.progress_updated.emit(self.current_progress)

    def _execute_command(self, command: List[str], operation_name: str):
        """
        주어진 명령어를 실행하고, 성공 여부를 확인합니다.
        실패 시 RuntimeError를 발생시킵니다.
        """
        logging.info(f"실행: {' '.join(command)}")
        return_code = -1
        # utils.run_command는 명령어 출력을 실시간으로 스트리밍하는 제너레이터입니다.
        for type, line in utils.run_command(command):
            self._check_stop()  # 매 출력 라인마다 중지 요청이 있었는지 확인합니다.
            if type == "stdout":
                logging.info(line)
            elif type == "stderr":
                logging.warning(f"오류 스트림: {line}")
            elif type == "return_code":
                return_code = int(line)

        # 명령어별 성공 조건이 다를 수 있으므로 분기하여 처리합니다.
        # robocopy는 파일 복사 성공 시에도 0이 아닌 값을 반환할 수 있습니다.
        is_success = (
            (return_code < 17)
            if "robocopy" in command[0].lower()
            else (return_code == 0)
        )
        if not is_success:
            # 작업 실패 시 예외를 발생시켜 run 메서드의 except 블록에서 처리하도록 합니다.
            raise RuntimeError(f"{operation_name} 실패. 종료 코드: {return_code}")

    def stop(self):
        """Controller에서 호출하여 스레드를 중지시키는 메서드입니다."""
        self._is_running = False

    def _check_stop(self):
        """스레드가 중지 요청을 받았는지 확인하고, 받았다면 UserCancelledError를 발생시킵니다."""
        if not self._is_running:
            raise UserCancelledError()

    def _setup_letters(self):
        """
        diskpart를 사용하여 OS 설치에 필요한 드라이브 문자를 할당하거나 해제합니다.
        - 클린 설치: 기존 C:, D:, Z: 문자를 모두 해제합니다.
        - 데이터 보존: 시스템, 데이터, 부트 볼륨에 각각 C:, D:, Z:를 명시적으로 할당합니다.
        """
        # 작업 전, 혹시 모를 충돌을 방지하기 위해 C, D, Z 드라이브 문자를 미리 해제합니다.
        cleanup_script = "\n".join(
            [
                "select vol c",
                "remove letter c",
                "select vol d",
                "remove letter d",
                "select vol z",
                "remove letter z",
            ]
        )
        success, output = utils.run_diskpart_script(cleanup_script)
        if not success:
            # 실패하더라도 치명적인 오류는 아닐 수 있으므로 경고만 로깅하고 계속 진행합니다.
            logging.warning(
                f"기존 문자 해제 중 오류가 발생했으나 무시하고 진행합니다: {output}"
            )

        # '데이터 보존' 옵션이 선택된 경우
        if self._options.save:
            info = self._system_info
            # Loader가 필요한 볼륨 인덱스를 모두 찾았는지 확인합니다.
            if not all(
                [
                    info.system_volume_index != -1,
                    info.data_volume_index != -1,
                    info.boot_volume_index != -1,
                ]
            ):
                raise RuntimeError(
                    "문자 할당 실패: 데이터 보존에 필요한 볼륨 정보를 찾을 수 없습니다."
                )
            # 찾은 인덱스를 기반으로 드라이브 문자를 할당하는 diskpart 스크립트를 생성합니다.
            assign_script_parts = [
                f"select volume {info.system_volume_index}",
                "assign letter=C",
                f"select volume {info.data_volume_index}",
                "assign letter=D",
                f"select volume {info.boot_volume_index}",
                "assign letter=Z",
            ]
            assign_script = "\n".join(assign_script_parts)
            success, output = utils.run_diskpart_script(assign_script)
            if not success:
                raise RuntimeError(f"diskpart 문자 할당 실패: {output}")

    def _format(self):
        """
        '데이터 보존' 여부에 따라 diskpart 스크립트를 동적으로 생성하여 디스크를 포맷합니다.
        - 데이터 보존: 시스템(C)과 부트(Z) 볼륨만 포맷합니다.
        - 클린 설치: 시스템 디스크와 데이터 디스크를 완전히 초기화(clean)하고 파티션을 새로 생성합니다.
        """
        script_lines = []
        info = self._system_info
        if self._options.save:  # '데이터 보존' 옵션
            if not all([info.system_volume_index != -1, info.boot_volume_index != -1]):
                raise RuntimeError(
                    "포맷 실패: 데이터 저장에 필요한 볼륨을 찾지 못했습니다."
                )
            # C 드라이브는 NTFS로, Z 드라이브(EFI)는 FAT32로 빠른 포맷합니다.
            script_lines = [
                "select volume c",
                "format fs=ntfs label=OS quick",
                "select volume z",
                "format fs=fat32 quick",
            ]
        else:  # '클린 설치' 옵션
            # 시스템 디스크와 데이터 디스크가 동일한 경우 (디스크 1개)
            if info.data_disk_index == -1 or (
                info.system_disk_index == info.data_disk_index
            ):
                if info.system_disk_index == -1:
                    raise RuntimeError(
                        "포맷 실패: 클린 설치에 필요한 시스템 디스크를 찾지 못했습니다."
                    )
                # 디스크를 초기화하고 EFI, OS(C), DATA(D) 파티션을 순서대로 생성합니다.
                script_lines = [
                    f"select disk {info.system_disk_index}",
                    "clean",
                    "convert gpt",
                    "create partition EFI size=100",
                    "format fs=fat32 quick",
                    "assign letter=Z",
                    "create partition primary size=153601",  # 약 150GB
                    "format fs=ntfs label=OS quick",
                    "assign letter=C",
                    "create partition primary",  # 나머지 공간 전체
                    "format fs=ntfs label=DATA quick",
                    "assign letter=D",
                ]
            # 시스템 디스크와 데이터 디스크가 다른 경우 (디스크 2개)
            elif info.system_disk_index != -1 and info.data_disk_index != -1:
                # 시스템 디스크(0번 디스크 가정)에는 EFI, OS 파티션을 생성합니다.
                script_lines = [
                    f"select disk {info.system_disk_index}",
                    "clean",
                    "convert gpt",
                    "create partition EFI size=100",
                    "format fs=fat32 quick",
                    "assign letter=Z",
                    "create partition primary",
                    "format fs=ntfs label=OS quick",
                    "assign letter=C",
                    # 데이터 디스크(1번 디스크 가정)에는 DATA 파티션만 생성합니다.
                    f"select disk {info.data_disk_index}",
                    "clean",
                    "convert gpt",
                    "create partition primary",
                    "format fs=ntfs label=DATA quick",
                    "assign letter=D",
                ]
            else:
                raise RuntimeError(
                    "포맷 실패: 클린 설치를 위한 디스크 구성을 결정할 수 없습니다."
                )

        script = "\n".join(script_lines)
        success, output = utils.run_diskpart_script(script)
        if not success:
            raise RuntimeError(f"diskpart 작업 실패: {output}")

    def _apply_image(self, start_progress: int, task_weight: int):
        """
        DISM 명령어를 사용하여 선택된 WIM 이미지 파일을 C 드라이브에 적용합니다.
        DISM 출력에서 진행률(%)을 파싱하여 UI 프로그레스 바를 실시간으로 업데이트합니다.
        """
        # PC 타입 ID에 맞는 WIM 파일 이름을 매핑합니다.
        wim_map = {
            0: "work.wim",
            1: "internet.wim",
            2: "trip.wim",
            3: "krnc.wim",
            4: "work.wim",
        }
        wim_filename = wim_map.get(self._options.type)
        if not wim_filename:
            raise ValueError(f"정의되지 않은 PC 타입: {self._options.type}")
        # WIM 파일의 전체 경로를 구성합니다. (예: C:/KdicSetup/wim/work.wim)
        wim_file_path = os.path.join(os.path.dirname(os.getcwd()), "wim", wim_filename)
        if not os.path.isfile(wim_file_path):
            raise FileNotFoundError(
                f"WIM 이미지 파일을 찾을 수 없습니다: {wim_file_path}"
            )

        # DISM 이미지 적용 명령어 리스트를 생성합니다.
        command = [
            "DISM.exe",
            "/Apply-Image",
            f"/ImageFile:{wim_file_path}",
            "/Index:1",  # WIM 파일 내의 첫 번째 이미지 사용
            "/ApplyDir:C:\\",  # 이미지를 적용할 대상 디렉토리
        ]

        logging.info(f"실행: {' '.join(command)}")
        return_code = -1
        for type, line in utils.run_command(command):
            self._check_stop()  # 중지 요청 확인
            # DISM 출력에서 "[  82.4%]"와 같은 진행률 텍스트를 찾습니다.
            progress_match = re.search(r"(\d{1,3}(?:\.\d+)?)%", line)
            if progress_match:
                # DISM의 진행률(0-100)을 이 작업의 가중치(task_weight)에 맞게 변환합니다.
                dism_progress = float(progress_match.group(1))
                gui_progress = start_progress + int(dism_progress / 100 * task_weight)
                self.progress_updated.emit(
                    gui_progress
                )  # 변환된 진행률을 UI에 업데이트

            if type == "stdout":
                logging.info(line)
            elif type == "stderr":
                logging.warning(f"오류 스트림: {line}")
            elif type == "return_code":
                return_code = int(line)
        if return_code != 0:
            raise RuntimeError(f"DISM 이미지 적용 실패. 종료 코드: {return_code}")

    def _install_drivers_with_dism(
        self, driver_path: str, start_progress: int, task_weight: int
    ):
        """
        DISM을 사용하여 오프라인 이미지(C 드라이브)에 드라이버를 설치합니다.
        '/Recurse' 옵션을 사용하여 지정된 드라이버 폴더의 하위 폴더까지 모두 검색합니다.
        DISM 출력에서 "Installing 1 of 54"와 같은 텍스트를 파싱하여 진행률을 업데이트합니다.
        """
        # DISM 드라이버 추가 명령어 리스트를 생성합니다.
        command = [
            "dism",
            "/image:C:\\",  # 대상 오프라인 이미지 경로
            "/add-driver",
            f"/driver:{driver_path}",  # 드라이버가 포함된 폴더 경로
            "/Recurse",  # 하위 폴더까지 모두 검색
        ]
        logging.info(f"실행: {' '.join(command)}")

        for type, line in utils.run_command(command):
            self._check_stop()  # 중지 요청 확인

            # "Installing 1 of 54" 또는 "1/54" 형식의 진행률 텍스트를 찾기 위한 정규 표현식
            progress_match = re.search(r"Installing (\d+) of (\d+)", line) or re.search(
                r"(\d+)/(\d+)", line
            )

            if progress_match:
                # 매치된 그룹에서 현재 드라이버 번호와 전체 드라이버 개수를 추출합니다.
                current_count = int(progress_match.group(1))
                total_count = int(progress_match.group(2))

                if total_count > 0:
                    # 현재 작업의 진행률(0.0 ~ 1.0)을 계산합니다.
                    task_progress = current_count / total_count
                    # 전체 진행률을 계산하여 UI에 업데이트합니다.
                    gui_progress = start_progress + int(task_progress * task_weight)
                    self.progress_updated.emit(gui_progress)

        # 루프가 끝나면(모든 드라이버 설치 완료), 이 작업에 할당된 가중치만큼 진행률을 더해 정확히 맞춥니다.
        self.progress_updated.emit(start_progress + task_weight)

    def _restore(self):
        """
        robocopy를 사용하여 사용자 폴더, 드라이버, 시작 메뉴 레이아웃 등 기타 설정 파일들을 복원합니다.
        작업 목록(restore_jobs)을 정의하고 순차적으로 실행합니다.
        '데이터 보존' 옵션에 따라 스티커 메모 복원 여부가 결정됩니다.
        """
        # 임시 파일들이 저장된 경로 (예: C:/KdicSetup/KdicSetup/Temp)
        temp_path = os.path.join(os.getcwd(), "Temp")
        # Loader가 찾은 현재 PC 모델에 맞는 드라이버 폴더 경로
        driver_source_path = self._system_info.driver_path
        # PC 타입에 따라 다른 시작 메뉴 레이아웃 파일(.bin) 경로를 설정합니다.
        start_menu_source_file = os.path.join(temp_path, "work", "start2.bin")
        if self._options.type not in [
            0,
            3,
            4,
        ]:  # 업무용, K자회사가 아닌 경우 (인터넷, 출장용)
            start_menu_source_file = os.path.join(temp_path, "internet", "start2.bin")
        # BitLocker 설정 여부에 따라 다른 무인 설치 응답 파일(unattend.xml) 경로를 설정합니다.
        unattend_source_path = os.path.join(
            os.path.dirname(os.getcwd()),
            "wim",
            "unattend_trip.xml" if self._options.bitlocker else "unattend_normal.xml",
        )

        restore_jobs = []
        # '데이터 보존' 시 C:\Users\kdic\ 에 있던 사용자 폴더들을 D:\kdic\ 로 복사합니다.
        user_folders_to_copy = [
            "Desktop",
            "Downloads",
            "Documents",
            "Pictures",
            "Music",
            "Videos",
        ]
        for folder in user_folders_to_copy:
            restore_jobs.append(
                {
                    "name": f"사용자 폴더({folder}) 복사",
                    "source": rf"C:\Users\kdic\{folder}",
                    "dest": rf"D:\kdic\{folder}",
                    "type": "folder",
                    "progress": 1,  # 작업 완료 시 증가시킬 진행률
                }
            )

        # 모든 경우에 공통적으로 수행할 복원 작업 목록
        common_jobs = [
            {
                "name": "드라이버 파일(C 드라이브) 복사",
                "source": driver_source_path,
                "dest": r"C:\SEPR\Drivers",  # 추후 사용을 위해 C드라이브에도 복사해둠
                "type": "folder",
                "progress": 0,
            },
            {
                "name": "시작 메뉴 레이아웃 복원",
                "source": start_menu_source_file,
                "dest": r"C:\Users\kdic\AppData\Local\Packages\Microsoft.Windows.StartMenuExperienceHost_cw5n1h2txyewy\LocalState",
                "type": "file",
                "progress": 1,
            },
            {
                "name": "Unattend.xml 파일 복사",
                "source": unattend_source_path,
                "dest": r"C:\Windows\system32\sysprep\unattend.xml",
                "type": "file-rename",  # shutil.copy를 사용하여 이름 변경 없이 복사
                "progress": 1,
            },
        ]
        restore_jobs.extend(common_jobs)

        # '데이터 보존' 옵션이 선택된 경우에만 스티커 메모 데이터를 복원합니다.
        if self._options.save:
            restore_jobs.append(
                {
                    "name": "스티커 메모 데이터 복원",
                    "source": os.path.join(temp_path, "StickyNotes"),
                    "dest": r"C:\Users\kdic\AppData\Local\Packages\Microsoft.MicrosoftStickyNotes_8wekyb3d8bbwe\LocalState",
                    "type": "folder",
                    "progress": 1,
                    "delete_source": True,  # 복원 후 임시 폴더 삭제
                }
            )

        # 정의된 작업 목록을 순회하며 실행합니다.
        for job in restore_jobs:
            self._check_stop()  # 중지 요청 확인
            source_path = job["source"]

            # 복사할 원본 파일/폴더가 존재하지 않으면 경고를 로깅하고 다음 작업으로 넘어갑니다.
            if not os.path.exists(source_path):
                # 단, C드라이브 드라이버 복사는 실패해도 무방하므로 경고를 띄우지 않습니다.
                if job["name"] != "드라이버 파일(C 드라이브) 복사":
                    logging.warning(
                        f"경고: 원본 '{source_path}'가 없어 '{job['name']}' 작업을 건너뜁니다."
                    )
                    self._update_progress(job["progress"])
                continue

            if job["type"] == "file-rename":
                # shutil을 사용하여 단순 파일 복사를 수행합니다.
                shutil.copy(source_path, job["dest"])
            else:
                # robocopy를 사용하여 폴더 또는 파일을 복사합니다.
                source_dir = source_path
                dest_dir = job["dest"]
                filename = None
                if (
                    job["type"] == "file"
                ):  # 파일 복사인 경우, 원본 경로에서 디렉토리와 파일명을 분리
                    source_dir = os.path.dirname(source_path)
                    filename = os.path.basename(source_path)

                # robocopy 명령어와 옵션을 리스트로 구성합니다.
                cmd_list = [
                    "robocopy",
                    source_dir,
                    dest_dir,
                ]
                if filename:
                    cmd_list.append(filename)

                cmd_list.extend(
                    [
                        "/E",  # 빈 디렉토리를 포함하여 하위 디렉토리 복사
                        "/COPYALL",  # 파일 정보(데이터, 속성, 타임스탬프, 보안 등) 모두 복사
                        "/B",  # 백업 모드로 복사 (권한 문제 회피)
                        "/R:1",  # 복사 실패 시 1번 재시도
                        "/W:1",  # 재시도 사이 1초 대기
                        "/J",  # 버퍼링되지 않은 I/O 사용 (대용량 파일에 유리)
                        "/MT:16",  # 16개의 스레드를 사용하여 멀티스레드 복사
                        "/NP",  # 진행률(%) 표시 안 함
                        "/NJS",  # 작업 요약 정보 표시 안 함
                        "/NJH",  # 작업 헤더 정보 표시 안 함
                    ]
                )

                self._execute_command(cmd_list, job["name"])

            # 'delete_source' 플래그가 True인 경우, 원본을 삭제합니다.
            if job.get("delete_source", False):
                try:
                    shutil.rmtree(source_path)
                    logging.info(f"임시 원본({source_path})을 삭제했습니다.")
                except Exception as e:
                    logging.warning(f"임시 원본({source_path}) 삭제 실패: {e}")

            # 작업이 성공적으로 끝나면 할당된 만큼 진행률을 업데이트합니다.
            if job["progress"] > 0:
                self._update_progress(job["progress"])

    def _configure_boot(self):
        """bcdboot와 bcdedit를 사용하여 UEFI 부트 파일을 생성하고 기본 부팅을 설정합니다."""
        # bcdboot: C:\Windows 폴더의 파일을 사용하여 부팅 환경을 Z 드라이브(EFI 파티션)에 생성합니다.
        # /s z: : 부팅 파일을 저장할 시스템 파티션을 지정합니다.
        # /f UEFI: UEFI 펌웨어용 부팅 파일을 생성하도록 지정합니다.
        bcdboot_command = ["bcdboot", r"C:\Windows", "/s", "z:", "/f", "UEFI"]
        self._execute_command(bcdboot_command, "부트 파일 생성")

        # bcdedit: 부팅 구성 데이터(BCD)를 편집합니다.
        # {default}는 기본 부팅 항목을 의미합니다.
        # device, osdevice를 모두 C: 파티션으로 설정하여 OS가 C에서 시작되도록 합니다.
        bcdedit_commands = [
            ["bcdedit", "/set", "{default}", "device", "partition=C:"],
            ["bcdedit", "/set", "{default}", "osdevice", "partition=C:"],
        ]
        for command in bcdedit_commands:
            self._execute_command(command, "기본 부팅 파티션 설정")
