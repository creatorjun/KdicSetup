# loader.py

# os 모듈: 파일 경로 생성, 디렉토리 존재 여부 확인 등 운영체제 관련 기능을 제공합니다.
import os

# re 모듈: 정규 표현식을 사용하여 문자열에서 특정 패턴을 찾거나 수정하는 데 사용됩니다.
import re

import winreg
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

            # --- [수정 1] 디스크 전체 크기 보정 로직 ---
            # detail disk의 볼륨 크기 합산으로 부정확한 list disk 크기 정보를 덮어씁니다.
            for disk in parsed_disks:
                if disk.size_gb == 0.0 and disk.volumes:
                    total_volume_size = sum(v.size_gb for v in disk.volumes)
                    if total_volume_size > 0:
                        disk.size_gb = round(total_volume_size, 2)

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
        """디스크 목록에서 'USB' 타입의 디스크를 필터링하여 제외합니다."""
        return [disk for disk in disks if "USB" not in disk.type.upper()]

    def _classify_volumes(self, disks: List[DiskInfo]) -> List[DiskInfo]:
        """
        볼륨 내 특정 폴더 구조를 기준으로 System, Data, Boot 볼륨을 자동으로 분류합니다.
        """
        system_candidates = []
        data_candidates = []

        for disk in disks:
            for volume in disk.volumes:
                if not volume.letter:
                    continue

                root = f"{volume.letter}:\\"
                sys_paths = {
                    "sysprep": os.path.join(root, "Windows", "system32", "sysprep"),
                    "desktop": os.path.join(root, "Users", "kdic", "desktop"),
                    "appdata": os.path.join(root, "Users", "kdic", "appdata"),
                }
                if all(os.path.isdir(p) for p in sys_paths.values()):
                    system_candidates.append(volume)

                kdic_desktop_path = os.path.join(root, "kdic", "desktop")
                kdic_downloads_path = os.path.join(root, "kdic", "downloads")
                if os.path.isdir(kdic_desktop_path) and os.path.isdir(
                    kdic_downloads_path
                ):
                    data_candidates.append(volume)

        for vol in system_candidates:
            vol.volume_type = "System"

        system_volume = system_candidates[0] if system_candidates else None
        data_candidates = [
            vol for vol in data_candidates if vol.volume_type != "System"
        ]

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
        레지스트리를 사용하여 메인보드 모델명을 조회하고, 일치하는 드라이버 폴더 경로를 반환합니다.
        (WMI 의존성 제거됨)
        """
        board_product_name = ""
        
        # 레지스트리 경로: HKEY_LOCAL_MACHINE\HARDWARE\DESCRIPTION\System\BIOS
        key_path = r"HARDWARE\DESCRIPTION\System\BIOS"

        try:
            # winreg를 사용하여 레지스트리 키를 엽니다.
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                # 'BaseBoardProduct' 값을 읽어옵니다. (대부분의 메인보드 모델명)
                try:
                    board_product_name, _ = winreg.QueryValueEx(key, "BaseBoardProduct")
                except FileNotFoundError:
                    # BaseBoardProduct가 없는 경우 'SystemProductName'을 시도합니다.
                    board_product_name, _ = winreg.QueryValueEx(key, "SystemProductName")
        except Exception:
            # 레지스트리 접근 실패 혹은 키를 찾을 수 없는 경우 무시하고 빈 문자열 유지
            pass

        if not board_product_name:
            raise RuntimeError("레지스트리를 통해 메인보드 모델명을 가져올 수 없습니다.")

        # 모델명에서 특수문자를 제거하고 공백을 정리합니다.
        clean_name = re.sub(r'[\\/:*?"<>|]', "", board_product_name).strip()
        
        # 드라이버 폴더 경로 설정 (현재 작업 디렉토리의 상위 폴더 -> Drivers)
        drivers_base_path = os.path.join(os.path.dirname(os.getcwd()), "Drivers")
        
        # 정리된 모델명으로 시작하는 폴더를 찾습니다.
        driver_path = self._find_path_by_prefix(drivers_base_path, clean_name)

        if not driver_path:
            raise FileNotFoundError(
                f"'{drivers_base_path}' 안에서 '{clean_name}'(으)로 시작하는 드라이버 폴더를 찾을 수 없습니다."
            )
        return driver_path

    def _find_path_by_prefix(self, base_path: str, prefix: str) -> str:
        """주어진 경로에서 특정 접두사로 시작하는 하위 폴더 경로를 찾습니다."""
        if not os.path.isdir(base_path):
            return ""
        for item in os.listdir(base_path):
            if item.lower().startswith(prefix.lower()):
                full_path = os.path.join(base_path, item)
                if os.path.isdir(full_path):
                    return full_path
        return ""

    def _read_completion_time(self, driver_path: str) -> int:
        """저장된 이전 작업 소요 시간을 읽어옵니다."""
        time_file_path = os.path.join(driver_path, "completion_time.txt")
        if os.path.exists(time_file_path):
            try:
                with open(time_file_path, "r") as f:
                    return int(f.read().strip())
            except (ValueError, IOError):
                return 0
        return 0

    def _get_disk_priority(self, disk: DiskInfo) -> int:
        """
        디스크 정렬을 위한 우선순위 정수를 반환합니다. (낮을수록 우선순위 높음)
        NVMe (0) > SSD (1) > 기타 HDD 등 (2)
        """
        type_upper = disk.type.upper()
        if "NVME" in type_upper:
            return 0  # 가장 높은 우선순위
        if "SSD" in type_upper:
            return 1  # 두 번째 우선순위
        return 2  # 가장 낮은 우선순위

    def _extract_system_info(
        self, disks: List[DiskInfo], driver_path: str, estimated_time: int
    ) -> SystemInfo:
        """
        분석된 모든 정보를 종합하여 최종 SystemInfo 객체를 생성합니다.
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

        # '데이터 보존' 옵션을 위해 기존 볼륨 정보를 우선 기록합니다.
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
        
        # --- 최종 디스크 구성 결정 로직 ---
        # 1차: 우선순위 점수, 2차: 디스크 전체 크기(작은 순)로 정렬합니다.
        sorted_disks = sorted(
            disks, key=lambda d: (self._get_disk_priority(d), d.size_gb)
        )

        # '클린 설치'를 위해 정렬된 디스크 목록을 기준으로 시스템/데이터 디스크를 재결정합니다.
        if sorted_disks:
            # 시스템 디스크는 항상 우선순위가 가장 높은 디스크로 지정합니다.
            info.system_disk_index = sorted_disks[0].index
            info.system_disk_type = sorted_disks[0].type

            # 데이터 디스크는 시스템 디스크가 아닌 디스크 중 가장 우선순위가 높은 것으로 지정합니다.
            if len(sorted_disks) > 1:
                data_disk_candidate = next((d for d in sorted_disks if d.index != info.system_disk_index), None)
                if data_disk_candidate:
                     info.data_disk_index = data_disk_candidate.index

        return info