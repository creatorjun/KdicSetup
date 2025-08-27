# models.py

# dataclasses 모듈: boilerplate 코드(반복적으로 작성해야 하는 코드) 없이
# 데이터 저장을 주 목적으로 하는 클래스를 쉽게 만들 수 있도록 도와줍니다.
# @dataclass 데ко레이터를 사용하면 __init__, __repr__ 같은 특수 메서드들이 자동으로 생성됩니다.
from dataclasses import dataclass, field

# typing 모듈: 타입 힌트를 제공하여 코드의 가독성을 높이고 잠재적인 오류를 방지합니다.
from typing import List


@dataclass
class Options:
    """
    사용자가 UI에서 선택한 설정 옵션을 저장하는 데이터 클래스입니다.
    Controller는 이 클래스의 인스턴스를 생성하여 Worker 스레드로 전달합니다.
    """

    type: int  # PC 타입 (0: 내부망, 1: 인터넷, 2: 출장용, 3: K자회사)
    save: bool  # 데이터 보존 여부 (True: 보존, False: 삭제)
    bitlocker: bool  # BitLocker 설정 여부 (True: 설정, False: 미설정)


@dataclass
class VolumeInfo:
    """
    디스크 내의 개별 볼륨(파티션)에 대한 상세 정보를 저장하는 데이터 클래스입니다.
    Loader가 diskpart 출력을 파싱하여 이 객체들을 생성합니다.
    """

    index: int  # 볼륨 번호 (예: 1, 2)
    letter: str  # 드라이브 문자 (예: 'C', 'D')
    label: str  # 볼륨 레이블(이름) (예: 'OS', 'DATA')
    filesystem: str  # 파일 시스템 (예: 'NTFS', 'FAT32')
    type: str  # 파티션 타입 (예: '주(Primary)', '시스템(System)')
    size_gb: float  # 볼륨 크기 (GB 단위)
    info: str = ""  # 추가 정보 (예: '부팅(Boot)', '페이지 파일(Pagefile)')
    # volume_type: Loader가 자체 로직으로 분류한 볼륨의 역할
    # (예: 'System', 'Data', 'Boot')
    volume_type: str = ""


@dataclass
class DiskInfo:
    """
    하나의 물리 디스크(SSD, HDD 등)에 대한 정보를 저장하는 데이터 클래스입니다.
    """

    index: int  # 디스크 번호 (예: 0, 1)
    type: str  # 디스크 타입 (예: 'NVMe', 'SSD', 'SATA')
    size_gb: float  # 디스크 전체 크기 (GB 단위)
    # 이 디스크에 속한 볼륨들의 리스트.
    # default_factory=list: DiskInfo 객체 생성 시 volumes 리스트를 빈 리스트로 초기화합니다.
    volumes: List[VolumeInfo] = field(default_factory=list)


@dataclass
class SystemInfo:
    """
    시스템 분석(Loader)이 완료된 후, 핵심 정보들을 종합하여 Worker 스레드에 전달하기 위한 데이터 클래스입니다.
    Worker는 이 정보를 바탕으로 자동화 작업을 수행합니다.
    """

    system_disk_index: int = -1  # OS가 설치되었거나 설치될 디스크의 인덱스
    system_disk_type: str = ""  # OS 디스크의 타입 (예: 'NVMe')
    data_disk_index: int = (
        -1
    )  # 데이터 저장용 디스크의 인덱스 (시스템 디스크와 같을 수 있음)
    system_volume_index: int = -1  # OS가 설치된 볼륨(C 드라이브)의 인덱스
    data_volume_index: int = -1  # 데이터가 저장된 볼륨(D 드라이브)의 인덱스
    boot_volume_index: int = -1  # 부팅 파티션(EFI, Z 드라이브) 볼륨의 인덱스
    system_volume_count: int = 0  # 발견된 시스템 볼륨('System'으로 분류된)의 총 개수
    driver_path: str = ""  # 현재 시스템에 맞는 드라이버가 위치한 폴더의 전체 경로
    estimated_time_sec: int = 0  # 이전에 저장된 작업 소요 시간 (초 단위)
