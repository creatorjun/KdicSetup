# models.py 수정 후

from dataclasses import dataclass, field
from typing import List


@dataclass
class Options:
    """사용자가 선택한 설정 옵션을 저장하는 데이터 클래스입니다."""

    type: int
    save: bool
    bitlocker: bool


@dataclass
class VolumeInfo:
    """디스크 볼륨(파티션)의 정보를 저장하는 데이터 클래스입니다."""

    index: int
    letter: str
    label: str
    filesystem: str
    type: str
    size_gb: float
    info: str = ""
    volume_type: str = ""


@dataclass
class DiskInfo:
    """물리 디스크의 정보를 저장하는 데이터 클래스입니다."""

    index: int
    type: str
    size_gb: float
    volumes: List[VolumeInfo] = field(default_factory=list)


@dataclass
class SystemInfo:
    """Loader가 분석을 마친 후 Controller/Worker에 전달할 핵심 정보."""

    system_disk_index: int = -1
    system_disk_type: str = ""
    data_disk_index: int = -1
    system_volume_index: int = -1
    data_volume_index: int = -1
    boot_volume_index: int = -1
    system_volume_count: int = 0