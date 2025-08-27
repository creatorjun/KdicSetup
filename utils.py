# utils.py

# re 모듈: 정규 표현식 처리를 위한 라이브러리입니다.
import re

# subprocess 모듈: 새로운 프로세스를 생성하고, 그들의 입출력 파이프에 연결하며, 반환 코드를 얻을 수 있게 해줍니다.
# 외부 명령어(diskpart, shutdown 등)를 실행하기 위해 사용됩니다.
import subprocess

# typing 모듈: 타입 힌트를 제공하여 코드의 명확성을 높이고 오류를 줄이는 데 도움을 줍니다.
from typing import Dict, List, Tuple, Generator

# models.py 파일에서 DiskInfo, VolumeInfo 데이터 클래스를 가져옵니다.
from models import DiskInfo, VolumeInfo

# logger.py 파일에서 함수 호출을 자동으로 로깅하는 데코레이터를 가져옵니다.
from logger import log_function_call

# ==============================================================================
# OS Command Utilities (운영체제 명령어 유틸리티)
# ==============================================================================


def run_command(command: List[str]) -> Generator[Tuple[str, str], None, None]:
    """
    주어진 명령어를 리스트 형태로 받아 실행하고, 표준 출력을 실시간으로 스트리밍하는 제너레이터를 반환합니다.
    이를 통해 DISM이나 robocopy 같이 실행 시간이 긴 명령어의 진행 상황을 실시간으로 UI에 표시할 수 있습니다.
    """
    try:
        # subprocess.Popen: 새로운 프로세스를 생성합니다.
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,  # 표준 출력을 파이프로 연결하여 읽을 수 있도록 함
            stderr=subprocess.PIPE,  # 표준 에러를 파이프로 연결
            text=True,  # 입출력을 텍스트 모드로 다룸
            encoding="cp949",  # 윈도우 한글 콘솔 인코딩(cp949)으로 디코딩
            shell=False,  # 보안 및 안정성을 위해 shell=False로 설정 (명령어를 문자열이 아닌 리스트로 받음)
            bufsize=1,  # 버퍼 크기를 1로 설정하여 라인 단위 버퍼링을 사용 (실시간 스트리밍)
            creationflags=subprocess.CREATE_NO_WINDOW,  # 실행 시 새로운 콘솔 창이 뜨지 않도록 함
        )

        # iter(process.stdout.readline, ""): stdout에서 한 줄씩 계속 읽어오다가, 빈 문자열(프로세스 종료)을 만나면 중단합니다.
        for line in iter(process.stdout.readline, ""):
            if not line:  # 빈 줄이면 루프를 빠져나감
                break
            # yield: 제너레이터가 값을 반환합니다. ('stdout', '실제 출력 내용') 튜플 형태입니다.
            yield "stdout", line.strip()

        # 프로세스가 완전히 종료될 때까지 기다리고, 종료 코드를 가져옵니다.
        return_code = process.wait()
        # 표준 에러 출력을 모두 읽어옵니다.
        stderr_output = process.stderr.read()
        if stderr_output:
            yield "stderr", stderr_output.strip()

        # 마지막으로 프로세스의 종료 코드를 반환합니다.
        yield "return_code", str(return_code)

    except FileNotFoundError:
        # command[0]에 해당하는 실행 파일을 찾을 수 없을 때 발생하는 예외입니다.
        yield "stderr", f"명령어를 찾을 수 없습니다: {command[0]}"
        yield "return_code", "-1"
    except Exception as e:
        # 그 외 예측하지 못한 예외가 발생했을 때 처리합니다.
        yield "stderr", f"명령어 실행 중 예외 발생: {e}"
        yield "return_code", "-1"


def run_diskpart_script(script_content: str) -> Tuple[bool, str]:
    """
    diskpart 스크립트 내용을 문자열로 받아 실행하고, 결과(성공여부, 전체 출력 텍스트)를 튜플로 반환합니다.
    Popen과 달리, 명령어 실행이 끝날 때까지 기다렸다가 결과를 한 번에 반환합니다.
    """
    try:
        # subprocess.run: 명령어를 실행하고 완료될 때까지 기다립니다.
        result = subprocess.run(
            ["diskpart"],
            input=script_content,  # 스크립트 내용을 표준 입력으로 전달
            capture_output=True,  # stdout, stderr를 캡처하여 result 객체에 저장
            text=True,
            encoding="cp949",
            shell=False,
            check=True,  # 종료 코드가 0이 아니면 CalledProcessError 예외 발생
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        # 성공 시 (True, 표준 출력 내용)을 반환합니다.
        return True, result.stdout
    except FileNotFoundError:
        return False, "diskpart 명령어를 찾을 수 없습니다. 프로그램 경로를 확인하세요."
    except subprocess.CalledProcessError as e:
        # check=True일 때, 명령어 실행이 실패하면 발생하는 예외입니다.
        return False, f"diskpart 실행 중 오류가 발생했습니다:\n{e.stderr}"
    except Exception as e:
        return False, f"알 수 없는 오류가 발생했습니다: {e}"


# ==============================================================================
# Parser Utilities (파서 유틸리티)
# ==============================================================================


def parse_list_disk(output: str) -> Tuple[List[str], Dict[str, str]]:
    """
    diskpart의 'list disk' 명령어 출력 텍스트를 파싱하여,
    디스크 인덱스 리스트와 (인덱스: 크기) 딕셔너리를 반환합니다.
    """
    indices = []  # 디스크 인덱스(번호)를 저장할 리스트
    sizes = {}  # {디스크 인덱스: 크기 문자열} 형태의 딕셔셔너리
    lines = output.splitlines()  # 입력 텍스트를 줄 단위로 분리
    header_found = False

    for line in lines:
        # '---' 라인을 만나면 그 다음부터 실제 데이터가 시작된다고 판단합니다.
        if "---" in line:
            header_found = True
            continue
        # 헤더를 만나기 전이거나 빈 줄은 건너뜁니다.
        if not header_found or not line.strip():
            continue

        parts = line.split()  # 공백을 기준으로 줄을 단어들로 분리
        # "디스크 1 온라인 931 GB 0 B" 와 같은 라인을 처리
        if len(parts) >= 4 and parts[0].lower() == "디스크":
            disk_index = parts[1]  # "1"

            size = ""
            unit = ""
            # 라인의 뒤에서부터 용량 단위를 찾습니다 (GB, MB 등).
            for i in range(len(parts) - 1, 2, -1):
                if parts[i].upper() in ("GB", "MB", "TB", "KB", "B"):
                    unit = parts[i]
                    size = parts[i - 1]
                    break

            # 크기와 단위를 모두 찾았으면 리스트와 딕셔너리에 추가합니다.
            if size and unit:
                indices.append(disk_index)
                sizes[disk_index] = f"{size} {unit}"  # 예: "931 GB"

    return indices, sizes


class Parser:
    """diskpart의 'detail disk' 결과 텍스트를 파싱하여 DiskInfo 객체 리스트로 변환하는 클래스"""

    @log_function_call
    def parse(self, output: str, disk_sizes: Dict[str, str]) -> List[DiskInfo]:
        """
        'detail disk' 명령어의 전체 출력과 'list disk'에서 얻은 크기 정보를 받아
        DiskInfo 객체 리스트를 생성하여 반환합니다.
        """
        disks = []
        # "디스크 1이(가) 선택한 디스크입니다." 와 같은 줄을 기준으로 전체 텍스트를 각 디스크별 정보로 분할합니다.
        disk_chunks = re.split(r"(\d+ 디스크가 선택한 디스크입니다.)", output)

        # 분할된 리스트는 [전 내용, 구분자1, 디스크1내용, 구분자2, 디스크2내용, ...] 형태가 됩니다.
        for i in range(1, len(disk_chunks), 2):
            separator_chunk = disk_chunks[i]  # 예: "1 디스크가 선택한 디스크입니다."
            content_chunk = disk_chunks[i + 1]  # 예: 디스크 1의 상세 정보 텍스트

            # 구분자에서 디스크 인덱스 번호를 추출합니다.
            disk_index_str = re.match(r"(\d+)", separator_chunk).group(1)
            disk_index = int(disk_index_str)

            # 디스크 유형(SATA, NVMe 등)을 추출합니다.
            type_match = re.search(r"유형\s+:\s+(.+)", content_chunk)
            disk_type_str = type_match.group(1).strip() if type_match else "알 수 없음"

            # 미리 파싱해둔 크기 정보를 가져옵니다.
            size_str = disk_sizes.get(disk_index_str, "0 GB")
            # DiskInfo 객체를 생성합니다.
            disk = DiskInfo(
                index=disk_index,
                type=disk_type_str,
                size_gb=self._convert_size_to_gb(size_str),
            )

            # 볼륨 정보 섹션 파싱 시작
            in_volume_section = False
            for line in content_chunk.splitlines():
                if "볼륨 ###" in line:
                    in_volume_section = True
                    continue

                if not in_volume_section or "--------" in line or not line.strip():
                    continue

                try:
                    # 두 칸 이상의 공백을 기준으로 줄을 분리하여 볼륨 정보를 추출합니다.
                    parts = re.split(r"\s{2,}", line.strip())

                    # "볼륨 1", "Volume 1" 등으로 시작하지 않는 줄은 건너뜁니다.
                    if not parts or not (
                        parts[0].lower().startswith("volume")
                        or parts[0].startswith("볼륨")
                    ):
                        continue

                    # "볼륨 1" 에서 숫자 "1"을 추출합니다.
                    vol_index_match = re.search(r"\d+", parts[0])
                    if not vol_index_match:
                        continue
                    vol_index = int(vol_index_match.group())

                    p = 1  # 파싱 위치를 가리키는 포인터

                    # 드라이브 문자(Ltr) 파싱
                    letter = ""
                    if (
                        p < len(parts)
                        and len(parts[p]) == 1
                        and "A" <= parts[p].upper() <= "Z"
                    ):
                        letter = parts[p]
                        p += 1

                    # 레이블(Label) 파싱 (파일 시스템 이름이 아니어야 함)
                    known_fs = {"NTFS", "FAT32", "FAT", "REFS", "FAT3"}
                    label = ""
                    if p < len(parts) and parts[p].upper() not in known_fs:
                        label = parts[p]
                        p += 1

                    # 파일 시스템(Fs), 유형(Type), 크기(Size) 파싱
                    filesystem = parts[p] if p < len(parts) else ""
                    p += 1
                    vol_type = parts[p] if p < len(parts) else ""
                    p += 1

                    vol_size_str = parts[p]
                    p += 1
                    # 크기 단위(GB, MB 등)가 다음 부분에 있을 경우 합쳐줍니다.
                    if p < len(parts) and parts[p] in ("GB", "MB", "KB", "B"):
                        vol_size_str += " " + parts[p]

                    # 파싱된 정보로 VolumeInfo 객체를 생성하여 disk.volumes 리스트에 추가합니다.
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
                    # 파싱 중 예상치 못한 형식의 라인이 있어도 오류를 내지 않고 넘어갑니다.
                    pass

            disks.append(disk)

        return disks

    def _convert_size_to_gb(self, size_str: str) -> float:
        """
        "931 GB", "500 MB" 와 같은 크기 문자열을 기가바이트(GB) 단위의 float으로 변환합니다.
        """
        size_str = size_str.strip().upper()
        # 정규 표현식으로 숫자 부분과 단위 부분을 분리합니다.
        match = re.match(r"(\d+\.?\d*)\s*(TB|GB|MB|KB|B)", size_str)
        if not match:
            return 0.0

        size = float(match.group(1))
        unit = match.group(2)

        # 단위를 기준으로 GB로 변환합니다.
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

        # 매우 작은 값(EFI 파티션 등)이 0으로 표시되지 않도록 최소 0.1로 보정합니다.
        if 0 < gb_value < 0.1:
            return 0.1

        # 소수점 둘째 자리까지 반올림하여 반환합니다.
        return round(gb_value, 2)


# ==============================================================================
# System Utilities (시스템 유틸리티)
# ==============================================================================


def reboot_system():
    """시스템을 즉시 재부팅합니다."""
    try:
        # shutdown 명령어 실행: /r (재부팅), /t 0 (0초 후 즉시)
        subprocess.run(
            ["shutdown", "/r", "/t", "0"],
            check=True,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return True, "시스템 재부팅 명령을 전송했습니다."
    except Exception as e:
        return False, f"재부팅 중 오류 발생: {e}"
