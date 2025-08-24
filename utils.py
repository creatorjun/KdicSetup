# utils.py

import re
import subprocess
from typing import Dict, List, Tuple, Generator
from models import DiskInfo, VolumeInfo
from logger import log_function_call

# ==============================================================================
# OS Command Utilities
# ==============================================================================


def run_command(command: List[str]) -> Generator[Tuple[str, str], None, None]:
    """
    주어진 명령어를 리스트 형태로 받아 실행하고, 표준 출력을 실시간으로 스트리밍하는 제너레이터를 반환합니다.
    """
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="cp949",
            shell=False,  # shell=True를 False로 변경
            bufsize=1,
        )

        for line in iter(process.stdout.readline, ""):
            if not line:
                break
            yield "stdout", line.strip()

        return_code = process.wait()
        stderr_output = process.stderr.read()
        if stderr_output:
            yield "stderr", stderr_output.strip()

        yield "return_code", str(return_code)

    except FileNotFoundError:
        # command가 리스트이므로 첫 번째 요소를 표시
        yield "stderr", f"명령어를 찾을 수 없습니다: {command[0]}"
        yield "return_code", "-1"
    except Exception as e:
        yield "stderr", f"명령어 실행 중 예외 발생: {e}"
        yield "return_code", "-1"


def run_diskpart_script(script_content: str) -> Tuple[bool, str]:
    """
    diskpart 스크립트 내용을 받아 실행하고, 결과 텍스트를 반환합니다.
    """
    try:
        result = subprocess.run(
            ["diskpart"],
            input=script_content,
            capture_output=True,
            text=True,
            encoding="cp949",
            shell=False,  # shell=True를 False로 변경
            check=True,
        )
        return True, result.stdout
    except FileNotFoundError:
        return False, "diskpart 명령어를 찾을 수 없습니다. 프로그램 경로를 확인하세요."
    except subprocess.CalledProcessError as e:
        return False, f"diskpart 실행 중 오류가 발생했습니다:\n{e.stderr}"
    except Exception as e:
        return False, f"알 수 없는 오류가 발생했습니다: {e}"


# ==============================================================================
# Parser Utilities
# (이하 내용은 변경 없음)
# ==============================================================================


# ... (기존 Parser 클래스 코드는 그대로 유지) ...
class Parser:
    """diskpart의 'detail disk' 결과 텍스트를 파싱하는 클래스"""

    @log_function_call
    def parse(self, output: str, disk_sizes: Dict[str, str]) -> List[DiskInfo]:
        disks = []
        disk_chunks = re.split(r"(\d+ 디스크가 선택한 디스크입니다.)", output)

        for i in range(1, len(disk_chunks), 2):
            separator_chunk = disk_chunks[i]
            content_chunk = disk_chunks[i + 1]

            disk_index_str = re.match(r"(\d+)", separator_chunk).group(1)
            disk_index = int(disk_index_str)

            type_match = re.search(r"유형\s+:\s+(.+)", content_chunk)
            disk_type_str = type_match.group(1).strip() if type_match else "알 수 없음"

            size_str = disk_sizes.get(disk_index_str, "0 GB")
            disk = DiskInfo(
                index=disk_index,
                type=disk_type_str,
                size_gb=self._convert_size_to_gb(size_str),
            )

            in_volume_section = False
            for line in content_chunk.splitlines():
                if "볼륨 ###" in line:
                    in_volume_section = True
                    continue

                if not in_volume_section or "--------" in line or not line.strip():
                    continue

                try:
                    parts = re.split(r"\s{2,}", line.strip())

                    if not parts or not (
                        parts[0].lower().startswith("volume")
                        or parts[0].startswith("볼륨")
                    ):
                        continue

                    vol_index_match = re.search(r"\d+", parts[0])
                    if not vol_index_match:
                        continue
                    vol_index = int(vol_index_match.group())

                    p = 1

                    letter = ""
                    if (
                        p < len(parts)
                        and len(parts[p]) == 1
                        and "A" <= parts[p].upper() <= "Z"
                    ):
                        letter = parts[p]
                        p += 1

                    known_fs = {"NTFS", "FAT32", "FAT", "REFS", "FAT3"}
                    label = ""
                    if p < len(parts) and parts[p].upper() not in known_fs:
                        label = parts[p]
                        p += 1

                    filesystem = parts[p] if p < len(parts) else ""
                    p += 1
                    vol_type = parts[p] if p < len(parts) else ""
                    p += 1

                    vol_size_str = parts[p]
                    p += 1
                    if p < len(parts) and parts[p] in ("GB", "MB", "KB", "B"):
                        vol_size_str += " " + parts[p]

                    disk.volumes.append(
                        VolumeInfo(
                            index=vol_index,
                            letter=letter,
                            label=label,
                            filesystem=filesystem,
                            type=vol_type,
                            size_gb=self._convert_size_to_gb(vol_size_str),
                        )
                    )
                except (ValueError, IndexError):
                    pass

            disks.append(disk)

        return disks

    def _convert_size_to_gb(self, size_str: str) -> float:
        size_str = size_str.strip().upper()
        match = re.match(r"(\d+\.?\d*)\s*(TB|GB|MB|KB|B)", size_str)
        if not match:
            return 0.0

        size = float(match.group(1))
        unit = match.group(2)

        gb_value = 0.0
        if unit == "TB":
            gb_value = size * 1024
        elif unit == "GB":
            gb_value = size
        elif unit == "MB":
            gb_value = size / 1024
        elif unit == "KB":
            gb_value = size / (1024**2)
        elif unit == "B":
            gb_value = size / (1024**3)

        if 0 < gb_value < 0.1:
            return 0.1

        return round(gb_value, 2)


# ==============================================================================
# System Utilities
# ==============================================================================


def reboot_system():
    """시스템을 즉시 재부팅합니다."""
    try:
        subprocess.run(
            ["shutdown", "/r", "/t", "0"], check=True, shell=False
        )  # shell=True를 False로 변경
        return True, "시스템 재부팅 명령을 전송했습니다."
    except Exception as e:
        return False, f"재부팅 중 오류 발생: {e}"
