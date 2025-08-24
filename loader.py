# loader.py

import os
import re
import wmi
import pythoncom
from typing import List, Dict, Tuple
from PyQt6.QtCore import QThread, pyqtSignal
from models import DiskInfo, SystemInfo
import utils


class Loader(QThread):
    """
    프로그램 시작 시 시스템의 하드웨어 정보를 분석하는 작업을 수행하는 스레드.
    UI 스레드와 분리하여 프로그램이 멈추는 현상을 방지합니다.
    """

    finished = pyqtSignal(object)  # 작업 완료 시 SystemInfo 객체를 전달하는 신호
    error_occurred = pyqtSignal(str)  # 오류 발생 시 오류 메시지를 전달하는 신호

    def run(self):
        """
        시스템 분석 작업의 전체 흐름을 제어하는 메인 실행 메서드.
        디스크 정보 수집, 파싱, 분류 및 드라이버 경로 확인 등 일련의 과정을 순차적으로 실행합니다.
        """
        try:
            # 1. 기본적인 디스크 목록 및 크기 정보 가져오기
            disk_indices, disk_sizes = self._get_base_disk_info()
            # 2. 각 디스크의 상세 정보(볼륨 포함) 가져오기
            detail_output = self._get_detailed_disk_info(disk_indices)
            # 3. 상세 정보 텍스트를 DiskInfo 객체 리스트로 변환
            parsed_disks = self._parse_disk_details(detail_output, disk_sizes)
            # 4. 드라이브 문자가 없는 볼륨에 문자 할당
            disks_with_letters = self._assign_drive_letters(parsed_disks)
            # 5. USB 디스크 제외
            internal_disks = self._filter_out_usb_disks(disks_with_letters)
            # 6. 볼륨의 역할을 System, Data, Boot 등으로 분류
            classified_disks = self._classify_volumes(internal_disks)
            # 7. 메인보드 모델명에 맞는 드라이버 폴더 경로 찾기
            driver_path = self._get_driver_path()
            # 8. 드라이버 폴더에 저장된 이전 작업 소요 시간 읽어오기
            estimated_time = self._read_completion_time(driver_path)
            # 9. 분석된 모든 정보를 종합하여 SystemInfo 객체 생성
            system_info = self._extract_system_info(
                classified_disks, driver_path, estimated_time
            )

            # 10. 분석 완료 신호와 함께 SystemInfo 객체 전달
            self.finished.emit(system_info)

        except Exception as e:
            # 작업 중 발생한 모든 예외를 처리하고 오류 신호 전달
            self.error_occurred.emit(str(e))

    def _get_base_disk_info(self) -> Tuple[List[str], Dict[str, str]]:
        """Diskpart를 실행하여 시스템의 기본 디스크 목록과 크기 정보를 가져옵니다."""
        success, list_disk_output = utils.run_diskpart_script("list disk")
        if not success:
            raise RuntimeError(
                f"디스크 목록을 가져오는 데 실패했습니다: {list_disk_output}"
            )

        disk_indices, disk_sizes = utils.parse_list_disk(list_disk_output)
        if not disk_indices:
            raise RuntimeError("설치된 디스크를 찾을 수 없습니다.")
        return disk_indices, disk_sizes

    def _get_detailed_disk_info(self, disk_indices: List[str]) -> str:
        """주어진 디스크 인덱스 목록에 대한 상세 정보를 Diskpart를 통해 가져옵니다."""
        detail_script = "\n".join(
            [f"select disk {i}\ndetail disk" for i in disk_indices]
        )
        success, detail_disk_output = utils.run_diskpart_script(detail_script)
        if not success:
            raise RuntimeError(
                f"디스크 상세 정보를 가져오는 데 실패했습니다: {detail_disk_output}"
            )
        return detail_disk_output

    def _parse_disk_details(
        self, detail_output: str, disk_sizes: Dict[str, str]
    ) -> List[DiskInfo]:
        """Diskpart의 상세 정보 텍스트 출력을 DiskInfo 객체 리스트로 파싱합니다."""
        parser = utils.Parser()
        return parser.parse(detail_output, disk_sizes)

    def _assign_drive_letters(self, disks: List[DiskInfo]) -> List[DiskInfo]:
        """드라이브 문자가 없는 볼륨에 실제 시스템 드라이브 문자를 할당합니다."""
        available_letters = [chr(ord("E") + i) for i in range(22)]

        for disk in disks:
            for volume in disk.volumes:
                if volume.letter and volume.letter in available_letters:
                    available_letters.remove(volume.letter)

        available_letters.sort(reverse=True)

        for disk in disks:
            for volume in disk.volumes:
                if not volume.letter and available_letters:
                    new_letter = available_letters.pop()
                    script = f"select volume {volume.index}\nassign letter={new_letter}"
                    success, _ = utils.run_diskpart_script(script)
                    if success:
                        volume.letter = new_letter
                    else:
                        available_letters.append(new_letter)
                        available_letters.sort(reverse=True)
        return disks

    def _filter_out_usb_disks(self, disks: List[DiskInfo]) -> List[DiskInfo]:
        """디스크 목록에서 USB 타입의 디스크를 필터링하여 제외합니다."""
        return [disk for disk in disks if "USB" not in disk.type.upper()]

    def _classify_volumes(self, disks: List[DiskInfo]) -> List[DiskInfo]:
        """
        볼륨 내 특정 폴더 구조를 기준으로 System, Data, Boot 볼륨을 분류합니다.
        이는 윈도우가 설치된 볼륨과 사용자 데이터가 저장된 볼륨을 식별하기 위함입니다.
        """
        system_candidates = []
        data_candidates = []

        for disk in disks:
            for volume in disk.volumes:
                if not volume.letter:
                    continue

                root = f"{volume.letter}:\\"
                # System 볼륨 조건: Windows, Users/kdic/desktop, Users/kdic/AppData 폴더 존재
                sys_paths = {
                    "sysprep": os.path.join(root, "Windows", "system32", "sysprep"),
                    "desktop": os.path.join(root, "Users", "kdic", "desktop"),
                    "appdata": os.path.join(root, "Users", "kdic", "appdata"),
                }
                if all(os.path.isdir(p) for p in sys_paths.values()):
                    system_candidates.append(volume)

                # --- [수정된 부분 시작] ---
                # Data 볼륨 조건: kdic/desktop, kdic/downloads 폴더가 모두 존재해야 함
                kdic_desktop_path = os.path.join(root, "kdic", "desktop")
                kdic_downloads_path = os.path.join(root, "kdic", "downloads")

                # 'and' 연산자를 사용하여 두 폴더가 모두 존재하는지 확인합니다.
                if os.path.isdir(kdic_desktop_path) and os.path.isdir(
                    kdic_downloads_path
                ):
                    data_candidates.append(volume)
                # --- [수정된 부분 끝] ---

        for vol in system_candidates:
            vol.volume_type = "System"

        system_volume = system_candidates[0] if system_candidates else None
        data_candidates = [
            vol for vol in data_candidates if vol.volume_type != "System"
        ]
        # 데이터 볼륨 후보가 여러 개일 경우, kdic 폴더 생성 날짜가 가장 최신인 것을 선택
        if len(data_candidates) > 1:
            try:
                data_volume = max(
                    data_candidates,
                    key=lambda vol: os.path.getctime(
                        os.path.join(f"{vol.letter}:\\", "kdic")
                    ),
                )
                data_volume.volume_type = "Data"
            except FileNotFoundError as e:
                raise RuntimeError(
                    f"데이터 볼륨 날짜 비교 중 폴더를 찾을 수 없습니다: {e}"
                )
        elif len(data_candidates) == 1:
            data_candidates[0].volume_type = "Data"

        # 시스템 볼륨이 있는 디스크에서 FAT32 파일 시스템을 가진 볼륨을 Boot 볼륨으로 분류
        if system_volume:
            system_disk_index = -1
            for disk in disks:
                if system_volume in disk.volumes:
                    system_disk_index = disk.index
                    break

            if system_disk_index != -1:
                for disk in disks:
                    if disk.index == system_disk_index:
                        for volume in disk.volumes:
                            if (
                                not volume.volume_type
                                and "FAT" in volume.filesystem.upper()
                            ):
                                volume.volume_type = "Boot"
                                break
        return disks

    def _get_driver_path(self) -> str:
        """
        WMI(Windows Management Instrumentation)를 사용하여 메인보드 모델명을 조회하고,
        해당 모델명으로 시작하는 드라이버 폴더의 전체 경로를 반환합니다.
        """
        board_product_name = ""
        try:
            pythoncom.CoInitialize()
            c = wmi.WMI()
            for board in c.Win32_BaseBoard():
                board_product_name = board.Product
        finally:
            pythoncom.CoUninitialize()

        if not board_product_name:
            raise RuntimeError("WMI를 통해 메인보드 모델명을 가져올 수 없습니다.")

        clean_name = re.sub(r'[\\/:*?"<>|]', "", board_product_name).strip()
        drivers_base_path = os.path.join(os.path.dirname(os.getcwd()), "Drivers")
        driver_path = self._find_path_by_prefix(drivers_base_path, clean_name)

        if not driver_path:
            raise FileNotFoundError(
                f"'{drivers_base_path}' 안에서 '{clean_name}'(으)로 시작하는 드라이버 폴더를 찾을 수 없습니다."
            )
        return driver_path

    def _find_path_by_prefix(self, base_path: str, prefix: str) -> str:
        """주어진 기본 경로에서 특정 접두사로 시작하는 하위 폴더의 전체 경로를 찾습니다."""
        if not os.path.isdir(base_path):
            return ""
        for item in os.listdir(base_path):
            if item.lower().startswith(prefix.lower()):
                full_path = os.path.join(base_path, item)
                if os.path.isdir(full_path):
                    return full_path
        return ""

    def _read_completion_time(self, driver_path: str) -> int:
        """
        드라이버 경로에 저장된 'completion_time.txt' 파일을 읽어
        이전 작업에서 소요된 시간을 초 단위 정수형으로 반환합니다.
        파일이 없거나 읽기 실패 시 0을 반환합니다.
        """
        time_file_path = os.path.join(driver_path, "completion_time.txt")
        if os.path.exists(time_file_path):
            try:
                with open(time_file_path, "r") as f:
                    return int(f.read().strip())
            except (ValueError, IOError):
                return 0
        return 0

    def _extract_system_info(
        self, disks: List[DiskInfo], driver_path: str, estimated_time: int
    ) -> SystemInfo:
        """
        분류된 볼륨 정보와 디스크 정보를 바탕으로 최종 SystemInfo 객체를 생성합니다.
        OS가 설치되지 않은 '클린 설치' 환경을 고려하여 시스템 디스크를 결정하는 로직을 포함합니다.
        """
        info = SystemInfo()
        info.driver_path = driver_path
        info.estimated_time_sec = estimated_time

        system_volume = next(
            (v for d in disks for v in d.volumes if v.volume_type == "System"), None
        )
        data_volume = next(
            (v for d in disks for v in d.volumes if v.volume_type == "Data"), None
        )
        boot_volume = next(
            (v for d in disks for v in d.volumes if v.volume_type == "Boot"), None
        )

        if system_volume:
            system_disk = next((d for d in disks if system_volume in d.volumes), None)
            if system_disk:
                info.system_disk_index = system_disk.index
                info.system_disk_type = system_disk.type
            info.system_volume_index = system_volume.index

        if data_volume:
            data_disk = next((d for d in disks if data_volume in d.volumes), None)
            if data_disk:
                info.data_disk_index = data_disk.index
            info.data_volume_index = data_volume.index

        if boot_volume:
            info.boot_volume_index = boot_volume.index

        info.system_volume_count = len(
            [v for d in disks for v in d.volumes if v.volume_type == "System"]
        )

        # 시스템 볼륨을 찾지 못한 경우(예: 새 디스크), 디스크 타입과 용량을 기준으로 시스템 디스크를 결정
        if info.system_disk_index == -1:
            sorted_disks = sorted(
                disks, key=lambda d: (self._get_disk_priority(d), d.size_gb)
            )

            if sorted_disks:
                info.system_disk_index = sorted_disks[0].index
                info.system_disk_type = sorted_disks[0].type
                # 디스크가 2개 이상이고 데이터 디스크가 아직 정해지지 않았다면 두 번째 디스크를 데이터 디스크로 지정
                if len(sorted_disks) > 1 and info.data_disk_index == -1:
                    info.data_disk_index = sorted_disks[1].index

        return info

    def _get_disk_priority(self, disk: DiskInfo) -> tuple:
        """디스크 정렬을 위한 우선순위 튜플 (NVMe > SSD > SATA)을 반환합니다."""
        type_upper = disk.type.upper()
        return (
            "NVME" not in type_upper,
            "SSD" not in type_upper,
            "SATA" not in type_upper,
        )
