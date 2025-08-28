# loader.py

# os 모듈: 파일 경로 생성, 디렉토리 존재 여부 확인 등 운영체제 관련 기능을 제공합니다.
import os

# re 모듈: 정규 표현식을 사용하여 문자열에서 특정 패턴을 찾거나 수정하는 데 사용됩니다.
import re

# wmi 모듈: Windows Management Instrumentation(WMI)에 접근하기 위한 라이브러리입니다.
# 시스템 하드웨어 정보(예: 메인보드 모델명)를 조회하기 위해 사용됩니다.
import wmi

# pythoncom 모듈: 파이썬에서 COM(Component Object Model) 객체를 사용하기 위해 필요합니다.
# wmi 모듈이 내부적으로 COM을 사용하므로, 스레드 환경에서 안전하게 사용하려면 초기화/해제가 필요합니다.
import pythoncom

# typing 모듈: 타입 힌트를 제공하여 코드의 가독성과 유지보수성을 향상시킵니다.
from typing import List, Dict, Tuple

# PyQt6.QtCore 모듈: Qt의 핵심 기능을 담고 있습니다.
# QThread: 시간이 오래 걸리는 작업을 별도 스레드에서 실행하여 GUI가 멈추는 것을 방지합니다.
# pyqtSignal: 스레드 간 안전한 통신을 위한 신호를 정의합니다.
from PyQt6.QtCore import QThread, pyqtSignal

# models.py와 utils.py에서 필요한 클래스와 함수를 가져옵니다.
from models import DiskInfo, SystemInfo
import utils


class Loader(QThread):
    """
    프로그램 시작 시 시스템의 하드웨어 정보를 분석하는 작업을 수행하는 스레드.
    UI 스레드와 분리하여 프로그램이 멈추는 현상을 방지합니다.
    """

    # finished 시그널: 작업이 성공적으로 완료되었을 때 SystemInfo 객체를 담아 Controller로 전달합니다.
    finished = pyqtSignal(object)
    # error_occurred 시그널: 작업 중 오류가 발생했을 때 오류 메시지(문자열)를 Controller로 전달합니다.
    error_occurred = pyqtSignal(str)

    def run(self):
        """
        QThread.start()가 호출되면 실행되는 메인 메서드입니다.
        시스템 분석 작업의 전체 흐름을 제어하며, 일련의 과정을 순차적으로 실행합니다.
        """
        try:
            # 1. diskpart를 이용해 기본적인 디스크 목록(인덱스)과 크기 정보를 가져옵니다.
            disk_indices, disk_sizes = self._get_base_disk_info()
            # 2. 각 디스크의 상세 정보(볼륨 목록 포함)를 가져옵니다.
            detail_output = self._get_detailed_disk_info(disk_indices)
            # 3. diskpart의 텍스트 출력을 파싱하여 DiskInfo 객체 리스트로 변환합니다.
            parsed_disks = self._parse_disk_details(detail_output, disk_sizes)
            # 4. 드라이브 문자가 없는 볼륨에 임시 드라이브 문자를 할당하여 내용에 접근할 수 있도록 합니다.
            disks_with_letters = self._assign_drive_letters(parsed_disks)
            # 5. 분석 대상에서 USB 디스크를 제외합니다.
            internal_disks = self._filter_out_usb_disks(disks_with_letters)
            # 6. 각 볼륨의 역할을 폴더 구조를 기반으로 System, Data, Boot 등으로 분류합니다.
            classified_disks = self._classify_volumes(internal_disks)
            # 7. WMI를 통해 메인보드 모델명을 조회하고, 일치하는 드라이버 폴더 경로를 찾습니다.
            driver_path = self._get_driver_path()
            # 8. 드라이버 폴더에 저장된 이전 작업의 소요 시간(completion_time.txt)을 읽어옵니다.
            estimated_time = self._read_completion_time(driver_path)
            # 9. 위에서 분석된 모든 정보를 종합하여 최종적으로 SystemInfo 객체를 생성합니다.
            system_info = self._extract_system_info(
                classified_disks, driver_path, estimated_time
            )

            # 10. 분석 완료를 알리는 'finished' 시그널에 SystemInfo 객체를 담아 보냅니다.
            self.finished.emit(system_info)

        except Exception as e:
            # 작업 중 발생한 모든 예외를 잡아 'error_occurred' 시그널로 오류 메시지를 보냅니다.
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
        # 각 디스크를 선택하고 상세 정보를 보는 diskpart 스크립트를 동적으로 생성합니다.
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
        """Diskpart의 상세 정보 텍스트 출력을 utils.Parser를 이용해 DiskInfo 객체 리스트로 변환합니다."""
        parser = utils.Parser()
        return parser.parse(detail_output, disk_sizes)

    def _assign_drive_letters(self, disks: List[DiskInfo]) -> List[DiskInfo]:
        """드라이브 문자가 없는 볼륨에 E:부터 시작하는 임시 드라이브 문자를 할당합니다."""
        # 할당 가능한 드라이브 문자 목록 (E ~ Z)
        available_letters = [chr(ord("E") + i) for i in range(22)]

        # 이미 사용 중인 문자는 목록에서 제거합니다.
        for disk in disks:
            for volume in disk.volumes:
                if volume.letter and volume.letter in available_letters:
                    available_letters.remove(volume.letter)

        # Z부터 거꾸로 할당하기 위해 리스트를 역순으로 정렬합니다.
        available_letters.sort(reverse=True)

        # 문자가 없는 볼륨을 찾아 문자를 할당합니다.
        for disk in disks:
            for volume in disk.volumes:
                if not volume.letter and available_letters:
                    new_letter = (
                        available_letters.pop()
                    )  # Z, Y, X... 순으로 문자를 꺼냄
                    script = f"select volume {volume.index}\nassign letter={new_letter}"
                    success, _ = utils.run_diskpart_script(script)
                    if success:
                        volume.letter = (
                            new_letter  # diskpart 할당 성공 시 객체에도 반영
                        )
                    else:
                        # 할당 실패 시, 사용하려던 문자를 다시 목록에 넣습니다.
                        available_letters.append(new_letter)
                        available_letters.sort(reverse=True)
        return disks

    def _filter_out_usb_disks(self, disks: List[DiskInfo]) -> List[DiskInfo]:
        """디스크 목록에서 'USB' 타입의 디스크를 필터링하여 제외합니다."""
        return [disk for disk in disks if "USB" not in disk.type.upper()]

    def _classify_volumes(self, disks: List[DiskInfo]) -> List[DiskInfo]:
        """
        볼륨 내 특정 폴더 구조를 기준으로 System, Data, Boot 볼륨을 자동으로 분류합니다.
        이는 윈도우가 설치된 볼륨과 사용자 데이터가 저장된 볼륨을 정확히 식별하기 위함입니다.
        """
        system_candidates = []  # 시스템 볼륨 후보 리스트
        data_candidates = []  # 데이터 볼륨 후보 리스트

        for disk in disks:
            for volume in disk.volumes:
                if not volume.letter:
                    continue

                root = f"{volume.letter}:\\"
                # ** 시스템 볼륨 조건 **
                # Windows, Users/kdic/desktop, Users/kdic/AppData 폴더가 모두 존재해야 함
                sys_paths = {
                    "sysprep": os.path.join(root, "Windows", "system32", "sysprep"),
                    "desktop": os.path.join(root, "Users", "kdic", "desktop"),
                    "appdata": os.path.join(root, "Users", "kdic", "appdata"),
                }
                if all(os.path.isdir(p) for p in sys_paths.values()):
                    system_candidates.append(volume)

                # ** 데이터 볼륨 조건 **
                # kdic/desktop 폴더와 kdic/downloads 폴더가 모두 존재해야 함
                kdic_desktop_path = os.path.join(root, "kdic", "desktop")
                kdic_downloads_path = os.path.join(root, "kdic", "downloads")
                if os.path.isdir(kdic_desktop_path) and os.path.isdir(
                    kdic_downloads_path
                ):
                    data_candidates.append(volume)

        # 찾은 시스템 볼륨 후보에 'System' 타입을 지정합니다.
        for vol in system_candidates:
            vol.volume_type = "System"

        # 시스템 볼륨은 유일하다고 가정하고 첫 번째 후보를 선택합니다.
        system_volume = system_candidates[0] if system_candidates else None
        # 데이터 볼륨 후보 중에서 시스템 볼륨으로 지정된 것은 제외합니다.
        data_candidates = [
            vol for vol in data_candidates if vol.volume_type != "System"
        ]

        # 데이터 볼륨 후보가 여러 개일 경우, 'kdic' 폴더의 생성 날짜가 가장 최신인 것을 최종 선택합니다.
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

        # ** 부트 볼륨(EFI) 분류 **
        # 시스템 볼륨이 있는 디스크 내에서, 아직 타입이 지정되지 않고 파일 시스템이 FAT/FAT32인 볼륨을 찾습니다.
        if system_volume:
            system_disk_index = -1
            # 시스템 볼륨이 속한 디스크의 인덱스를 찾습니다.
            for disk in disks:
                if system_volume in disk.volumes:
                    system_disk_index = disk.index
                    break

            # 해당 디스크 내에서 부트 볼륨을 찾습니다.
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
        WMI를 사용하여 메인보드 모델명을 조회하고,
        ../Drivers/ 폴더 아래에서 해당 모델명으로 시작하는 드라이버 폴더의 전체 경로를 반환합니다.
        """
        board_product_name = ""
        try:
            # 스레드에서 COM 객체를 사용하기 전에 초기화합니다.
            pythoncom.CoInitialize()
            c = wmi.WMI()
            # Win32_BaseBoard 클래스에서 메인보드 정보를 조회합니다.
            for board in c.Win32_BaseBoard():
                board_product_name = board.Product
        finally:
            # COM 사용이 끝나면 해제합니다.
            pythoncom.CoUninitialize()

        if not board_product_name:
            raise RuntimeError("WMI를 통해 메인보드 모델명을 가져올 수 없습니다.")

        # 파일/폴더 이름으로 사용할 수 없는 특수 문자를 제거합니다.
        clean_name = re.sub(r'[\\/:*?"<>|]', "", board_product_name).strip()
        # 드라이버가 저장된 기본 경로를 설정합니다 (예: C:/KdicSetup/Drivers)
        drivers_base_path = os.path.join(os.path.dirname(os.getcwd()), "Drivers")
        # 정리된 모델명으로 시작하는 폴더를 찾습니다.
        driver_path = self._find_path_by_prefix(drivers_base_path, clean_name)

        if not driver_path:
            raise FileNotFoundError(
                f"'{drivers_base_path}' 안에서 '{clean_name}'(으)로 시작하는 드라이버 폴더를 찾을 수 없습니다."
            )
        return driver_path

    def _find_path_by_prefix(self, base_path: str, prefix: str) -> str:
        """주어진 기본 경로(base_path)에서 특정 접두사(prefix)로 시작하는 하위 폴더의 전체 경로를 찾습니다."""
        if not os.path.isdir(base_path):
            return ""
        for item in os.listdir(base_path):
            # 대소문자 구분 없이 비교합니다.
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
        분류된 볼륨 정보와 디스크 정보를 바탕으로 최종 SystemInfo 객체를 생성하여 반환합니다.
        OS가 설치되지 않은 '클린 설치' 환경을 고려하여 시스템 디스크를 결정하는 로직을 포함합니다.
        """
        info = SystemInfo()
        info.driver_path = driver_path
        info.estimated_time_sec = estimated_time

        # 분류된 볼륨들을 찾습니다.
        system_volume = next(
            (v for d in disks for v in d.volumes if v.volume_type == "System"), None
        )
        data_volume = next(
            (v for d in disks for v in d.volumes if v.volume_type == "Data"), None
        )
        boot_volume = next(
            (v for d in disks for v in d.volumes if v.volume_type == "Boot"), None
        )

        # 각 볼륨이 존재하면, 해당 볼륨 및 디스크의 인덱스 정보를 SystemInfo 객체에 저장합니다.
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

        # 발견된 시스템 볼륨의 총 개수를 저장합니다.
        info.system_volume_count = len(
            [v for d in disks for v in d.volumes if v.volume_type == "System"]
        )

        # ** 디스크 구성 최종 결정 **
        # 우선순위(NVMe > SSD > SATA)와 용량(작은 순)에 따라 디스크를 정렬합니다.
        sorted_disks = sorted(
            disks, key=lambda d: (self._get_disk_priority(d), d.size_gb)
        )

        # 1. 시스템 디스크 결정:
        # 만약 볼륨 분석으로 시스템 디스크를 찾지 못했다면 (클린 디스크),
        # 정렬된 디스크 목록의 첫 번째 디스크를 시스템 디스크로 지정합니다.
        if info.system_disk_index == -1 and sorted_disks:
            info.system_disk_index = sorted_disks[0].index
            info.system_disk_type = sorted_disks[0].type

        # 2. 데이터 디스크 결정:
        # 만약 볼륨 분석으로 데이터 디스크를 찾지 못했고, 디스크가 2개 이상이라면,
        # 시스템 디스크가 아닌 다른 디스크를 데이터 디스크로 지정합니다.
        if info.data_disk_index == -1 and len(sorted_disks) > 1:
            # 시스템 디스크로 지정된 디스크를 제외한 첫 번째 디스크를 데이터 디스크 후보로 선택합니다.
            for disk in sorted_disks:
                if disk.index != info.system_disk_index:
                    info.data_disk_index = disk.index
                    break  # 데이터 디스크를 찾았으므로 루프 종료

        return info

    def _get_disk_priority(self, disk: DiskInfo) -> tuple:
        """
        디스크 정렬을 위한 우선순위 튜플을 반환합니다. (NVMe > SSD > SATA)
        튜플의 각 항목이 False일수록(즉, 타입 문자열을 포함할수록) 우선순위가 높습니다.
        """
        type_upper = disk.type.upper()
        return (
            "NVME" not in type_upper,  # NVMe가 아니면 True (우선순위 낮음)
            "SSD" not in type_upper,  # SSD가 아니면 True
            "SATA" not in type_upper,  # SATA가 아니면 True
        )
