# -*- coding: utf-8 -*-
import os
import re
import shutil
import logging

from PyQt6.QtCore import QThread, pyqtSignal

import utils
from models import Options, SystemInfo


class UserCancelledError(Exception):
    """사용자가 작업을 중단했을 때 발생하는 예외입니다."""

    pass


class Worker(QThread):
    progress_updated = pyqtSignal(int)
    log_updated = pyqtSignal(str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, options: Options, system_info: SystemInfo):
        super().__init__()
        self._options = options
        self._system_info = system_info
        self._is_running = True
        self.current_progress = 0

    def run(self):
        """자동화 작업의 흐름을 제어하는 오케스트레이터."""
        try:
            type_map = {
                0: "업무용",
                1: "인터넷용",
                2: "출장용",
                3: "K자회사",
                4: "업무용",
            }
            pc_type_str = type_map.get(self._options.type, "알 수 없음")
            save_str = "보존" if self._options.save else "삭제"

            start_message = (
                f"데이터를 {save_str}하고 '{pc_type_str}'(으)로 초기화합니다."
            )
            self.log_updated.emit(start_message)

            self._setup_letters()
            self._update_progress(1)
            self._format()
            self._update_progress(1)

            apply_task_weight = 80
            self._apply_image(
                start_progress=self.current_progress, task_weight=apply_task_weight
            )
            self.current_progress += apply_task_weight

            driver_path = self._system_info.driver_path

            driver_task_weight = 10
            self._install_drivers_with_dism(
                driver_path,
                start_progress=self.current_progress,
                task_weight=driver_task_weight,
            )
            self.current_progress += driver_task_weight

            self._restore()

            self._configure_boot()
            self._update_progress(1)

            self.progress_updated.emit(100)
            self.finished.emit()

        except UserCancelledError:
            pass
        except Exception as e:
            logging.exception("Worker.run에서 처리되지 않은 예외 발생")
            self.error_occurred.emit(f"작업 중 오류 발생: {e}")

    def _update_progress(self, value: int):
        self.current_progress += value
        self.progress_updated.emit(self.current_progress)

    def _execute_command(self, command: str, operation_name: str):
        logging.info(f"실행: {command}")
        return_code = -1
        for type, line in utils.run_command(command):
            self._check_stop()
            if type == "stdout":
                logging.info(line)
            elif type == "stderr":
                logging.warning(f"오류 스트림: {line}")
            elif type == "return_code":
                return_code = int(line)

        is_success = (
            (return_code < 17) if "robocopy" in command.lower() else (return_code == 0)
        )
        if not is_success:
            raise RuntimeError(f"{operation_name} 실패. 종료 코드: {return_code}")

    def stop(self):
        self._is_running = False

    def _check_stop(self):
        if not self._is_running:
            raise UserCancelledError()

    def _setup_letters(self):
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
            logging.warning(
                f"기존 문자 해제 중 오류가 발생했으나 무시하고 진행합니다: {output}"
            )
        if self._options.save:
            info = self._system_info
            if not all(
                [
                    info.system_volume_index != -1,
                    info.data_volume_index != -1,
                    info.boot_volume_index != -1,
                ]
            ):
                raise RuntimeError("문자 할당 실패")
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
        script_lines = []
        info = self._system_info
        if self._options.save:
            if not all([info.system_volume_index != -1, info.boot_volume_index != -1]):
                raise RuntimeError(
                    "포맷 실패: 데이터 저장에 필요한 볼륨을 찾지 못했습니다."
                )
            script_lines = [
                "select volume c",
                "format fs=ntfs label=OS quick",
                "select volume z",
                "format fs=fat32 quick",
            ]
        else:
            if info.data_disk_index == -1 or (
                info.system_disk_index == info.data_disk_index
            ):
                if info.system_disk_index == -1:
                    raise RuntimeError(
                        "포맷 실패: 클린 설치에 필요한 시스템 디스크를 찾지 못했습니다."
                    )

                script_lines = [
                    f"select disk {info.system_disk_index}",
                    "clean",
                    "convert gpt",
                    "create partition EFI size=100",
                    "format fs=fat32 quick",
                    "assign letter=Z",
                    "create partition primary size=153601",
                    "format fs=ntfs label=OS quick",
                    "assign letter=C",
                    "create partition primary",
                    "format fs=ntfs label=DATA quick",
                    "assign letter=D",
                ]
            elif info.system_disk_index != -1 and info.data_disk_index != -1:
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
        wim_file_path = os.path.join(os.path.dirname(os.getcwd()), "wim", wim_filename)
        if not os.path.isfile(wim_file_path):
            raise FileNotFoundError(
                f"WIM 이미지 파일을 찾을 수 없습니다: {wim_file_path}"
            )
        command = f'DISM.exe /Apply-Image /ImageFile:"{wim_file_path}" /Index:1 /ApplyDir:C:\\'

        logging.info(f"실행: {command}")
        return_code = -1
        for type, line in utils.run_command(command):
            self._check_stop()
            progress_match = re.search(r"(\d{1,3}(?:\.\d+)?)%", line)
            if progress_match:
                dism_progress = float(progress_match.group(1))
                gui_progress = start_progress + int(dism_progress / 100 * task_weight)
                self.progress_updated.emit(gui_progress)
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
        """DISM을 사용하여 드라이버를 설치하고, n/n 형식의 출력을 파싱하여 진행률을 업데이트합니다."""
        command = f'dism /image:C:\\ /add-driver /driver:"{driver_path}" /Recurse'
        logging.info(f"실행: {command}")

        for type, line in utils.run_command(command):
            self._check_stop()

            progress_match = re.search(r"Installing (\d+) of (\d+)", line) or re.search(
                r"(\d+)/(\d+)", line
            )

            if progress_match:
                current_count = int(progress_match.group(1))
                total_count = int(progress_match.group(2))

                if total_count > 0:
                    task_progress = current_count / total_count
                    gui_progress = start_progress + int(task_progress * task_weight)
                    self.progress_updated.emit(gui_progress)

        self.progress_updated.emit(start_progress + task_weight)

    def _restore(self):
        """
        사용자 폴더, 드라이버, 시작 메뉴 레이아웃 등 기타 설정 파일들을 복원합니다.
        '데이터 보존' 옵션에 따라 스티커 메모 복원 여부가 결정됩니다.
        """
        temp_path = os.path.join(os.getcwd(), "Temp")
        driver_source_path = self._system_info.driver_path
        start_menu_source_file = os.path.join(temp_path, "work", "start2.bin")
        if self._options.type not in [0, 3, 4]:
            start_menu_source_file = os.path.join(temp_path, "internet", "start2.bin")
        unattend_source_path = os.path.join(
            os.path.dirname(os.getcwd()),
            "wim",
            "unattend_trip.xml" if self._options.bitlocker else "unattend_normal.xml",
        )

        # 복원할 작업 목록 정의
        restore_jobs = []

        # 사용자 폴더 복사 작업은 항상 수행
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
                    "progress": 1,
                }
            )

        # 모든 경우에 공통적으로 수행할 복원 작업 추가
        common_jobs = [
            {
                "name": "드라이버 파일(C 드라이브) 복사",
                "source": driver_source_path,
                "dest": r"C:\SEPR\Drivers",
                "type": "folder",
                "progress": 1,
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
                "type": "file-rename",
                "progress": 3,
            },
        ]
        restore_jobs.extend(common_jobs)

        # '데이터 보존' 옵션이 선택된 경우에만 스티커 메모 복원 작업을 추가
        if self._options.save:
            restore_jobs.append(
                {
                    "name": "스티커 메모 데이터 복원",
                    "source": os.path.join(temp_path, "StickyNotes"),
                    "dest": r"C:\Users\kdic\AppData\Local\Packages\Microsoft.MicrosoftStickyNotes_8wekyb3d8bbwe\LocalState",
                    "type": "folder",
                    "progress": 1,
                    "delete_source": True,
                }
            )

        # 정의된 작업 목록을 순차적으로 실행
        for job in restore_jobs:
            self._check_stop()
            source_path = job["source"]

            # 원본 경로가 존재하지 않으면 경고 로그를 남기고 작업을 건너뜀
            if not os.path.exists(source_path):
                logging.warning(
                    f"경고: 원본 '{source_path}'가 없어 '{job['name']}' 작업을 건너뜁니다."
                )
                self._update_progress(job["progress"])
                continue

            # 파일 또는 폴더 복사 실행
            if job["type"] == "file-rename":
                shutil.copy(source_path, job["dest"])
            else:
                source_dir = source_path
                dest_dir = job["dest"]
                filename = None
                if job["type"] == "file":
                    source_dir = os.path.dirname(source_path)
                    filename = os.path.basename(source_path)

                # Robocopy 명령어에 재시도 옵션(/R:1, /W:1)을 명시적으로 포함
                cmd = (
                    f'robocopy "{source_dir}" "{dest_dir}"'
                    f"{' ' + filename if filename else ''}"
                    " /E /COPYALL /B /R:1 /W:1 /J /MT:16 /NP /NJS /NJH"
                )
                self._execute_command(cmd, job["name"])

            # 작업 완료 후 임시 원본 삭제 옵션이 있으면 삭제
            if job.get("delete_source", False):
                try:
                    shutil.rmtree(source_path)
                    logging.info(f"임시 원본({source_path})을 삭제했습니다.")
                except Exception as e:
                    logging.warning(f"임시 원본({source_path}) 삭제 실패: {e}")
            self._update_progress(job["progress"])

    def _configure_boot(self):
        """bcdboot와 bcdedit를 사용하여 UEFI 부트 파일을 생성하고 기본 부팅을 설정합니다."""
        # 1. bcdboot로 부트 파일 생성 및 기본 항목 등록
        bcdboot_command = r"bcdboot C:\Windows /s z: /f UEFI"
        self._execute_command(bcdboot_command, "부트 파일 생성")

        # 2. bcdedit로 {default} 부팅 항목이 C 드라이브를 가리키도록 명시적으로 설정
        bcdedit_commands = [
            r"bcdedit /set {default} device partition=C:",
            r"bcdedit /set {default} osdevice partition=C:",
        ]
        for command in bcdedit_commands:
            self._execute_command(command, "기본 부팅 파티션 설정")
