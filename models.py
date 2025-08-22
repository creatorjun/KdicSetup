# models.py

from dataclasses import dataclass, field
from typing import List


@dataclass
class Options:
    """사용자가 UI에서 선택한 설정 옵션을 저장하는 데이터 클래스입니다."""

    type: int  # PC 타입 (0: 내부망, 1: 인터넷, 2: 출장용, 3: K자회사)
    save: bool  # 데이터 보존 여부
    bitlocker: bool  # BitLocker 설정 여부


@dataclass
class VolumeInfo:
    """디스크 내 개별 볼륨(파티션)의 상세 정보를 저장하는 데이터 클래스입니다."""

    index: int  # 볼륨 번호
    letter: str  # 드라이브 문자 (예: C, D)
    label: str  # 볼륨 레이블 (예: OS, DATA)
    filesystem: str  # 파일 시스템 (예: NTFS, FAT32)
    type: str  # 파티션 타입 (예: 주, 시스템)
    size_gb: float  # 볼륨 크기 (GB)
    info: str = ""  # 추가 정보 (예: 부팅, 페이지 파일)
    volume_type: str = (
        ""  # 프로그램에서 자체적으로 분류한 볼륨 역할 (System, Data, Boot)
    )


@dataclass
class DiskInfo:
    """하나의 물리 디스크 정보를 저장하는 데이터 클래스입니다."""

    index: int  # 디스크 번호
    type: str  # 디스크 타입 (예: NVMe, SSD, SATA)
    size_gb: float  # 디스크 전체 크기 (GB)
    volumes: List[VolumeInfo] = field(default_factory=list)  # 디스크에 속한 볼륨 목록


@dataclass
class SystemInfo:
    """시스템 분석 후 Worker에 전달될 핵심 정보를 종합하는 데이터 클래스입니다."""

    system_disk_index: int = -1  # OS가 설치된 디스크의 인덱스
    system_disk_type: str = ""  # OS가 설치된 디스크의 타입
    data_disk_index: int = -1  # 데이터 저장용 디스크의 인덱스
    system_volume_index: int = -1  # OS가 설치된 볼륨의 인덱스
    data_volume_index: int = -1  # 데이터가 저장된 볼륨의 인덱스
    boot_volume_index: int = -1  # 부팅 파티션(EFI) 볼륨의 인덱스
    system_volume_count: int = 0  # 발견된 시스템 볼륨의 총 개수
    driver_path: str = ""  # 현재 시스템에 맞는 드라이버가 위치한 폴더 경로
    estimated_time_sec: int = 0  # 이전에 저장된 작업 소요 시간 (초)
