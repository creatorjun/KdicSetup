# loader.py 수정 후

import os
from typing import List, Dict, Tuple
from PyQt6.QtCore import QThread, pyqtSignal
from models import DiskInfo, SystemInfo
import utils


class Loader(QThread):
    finished = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def run(self):
        """작업 흐름을 제어하는 메인 실행 메서드."""
        try:
            disk_indices, disk_sizes = self._get_base_disk_info()
            detail_output = self._get_detailed_disk_info(disk_indices)
            parsed_disks = self._parse_disk_details(detail_output, disk_sizes)
            disks_with_letters = self._assign_drive_letters(parsed_disks)
            internal_disks = self._filter_out_usb_disks(disks_with_letters)
            classified_disks = self._classify_volumes(internal_disks)
            system_info = self._extract_system_info(classified_disks)

            self.finished.emit(system_info)

        except Exception as e:
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

                    success, output = utils.run_diskpart_script(script)

                    if success:
                        volume.letter = new_letter
                    else:
                        available_letters.append(new_letter)
                        available_letters.sort(reverse=True)
                        # 에러 발생 시 콘솔에 로그를 남길 수 있습니다.
                        # print(f"실패: Volume {volume.index} 문자 할당 실패: {output}")

        return disks

    def _filter_out_usb_disks(self, disks: List[DiskInfo]) -> List[DiskInfo]:
        """디스크 목록에서 USB 타입의 디스크를 필터링하여 제외합니다."""
        return [disk for disk in disks if "USB" not in disk.type.upper()]

    def _classify_volumes(self, disks: List[DiskInfo]) -> List[DiskInfo]:
        """특정 폴더 구조를 기준으로 System/Data/Boot 볼륨을 분류합니다."""
        system_candidates = []
        data_candidates = []

        for disk in disks:
            for volume in disk.volumes:
                if not volume.letter:
                    continue

                root = f"{volume.letter}:\\"

                # System 볼륨 조건: 3개 폴더가 모두 존재
                sys_paths = {
                    "sysprep": os.path.join(root, "Windows", "system32", "sysprep"),
                    "desktop": os.path.join(root, "Users", "kdic", "desktop"),
                    "appdata": os.path.join(root, "Users", "kdic", "AppData"),
                }
                if all(os.path.isdir(p) for p in sys_paths.values()):
                    system_candidates.append(volume)

                # Data 볼륨 조건: 2개 폴더가 모두 존재
                data_paths = {
                    "kdic_desktop": os.path.join(root, "kdic", "desktop"),
                    "kdic_appdata": os.path.join(root, "kdic", "AppData"),
                }
                if all(os.path.isdir(p) for p in data_paths.values()):
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

    def _get_disk_priority(self, disk: DiskInfo) -> tuple:
        """디스크 정렬을 위한 우선순위 튜플 (NVMe > SSD > SATA)을 반환합니다."""
        type_upper = disk.type.upper()
        return (
            "NVMe" not in type_upper,
            "SSD" not in type_upper,
            "SATA" not in type_upper,
        )

    # --- _identify_disk_roles 메소드는 삭제됨 ---

    def _extract_system_info(self, disks: List[DiskInfo]) -> SystemInfo:
        """
        [수정됨] 볼륨 타입(volume_type)을 직접 사용하여 디스크 인덱스를 추출하고,
        클린 설치 시에는 디스크 타입과 '용량'을 기준으로 시스템 디스크를 결정합니다.
        """
        info = SystemInfo()

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

        if info.system_disk_index == -1:
            sorted_disks = sorted(
                disks, key=lambda d: (self._get_disk_priority(d), d.size_gb)
            )

            if sorted_disks:
                info.system_disk_index = sorted_disks[0].index
                info.system_disk_type = sorted_disks[0].type
                if len(sorted_disks) > 1 and info.data_disk_index == -1:
                    info.data_disk_index = sorted_disks[1].index

        return info
