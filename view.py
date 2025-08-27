# view.py

# PyQt6.QtCore 모듈에서 pyqtSignal 클래스를 가져옵니다.
# pyqtSignal: 사용자 정의 시그널을 생성하여 객체 간의 통신을 가능하게 합니다.
from PyQt6.QtCore import pyqtSignal

# PyQt6.QtWidgets 모듈에서 GUI 구성에 필요한 다양한 위젯 클래스들을 가져옵니다.
from PyQt6.QtWidgets import (
    QApplication,  # 애플리케이션 객체
    QMainWindow,  # 메인 윈도우
    QWidget,  # 모든 UI 객체의 기본이 되는 위젯
    QVBoxLayout,  # 위젯을 수직으로 배치하는 레이아웃
    QHBoxLayout,  # 위젯을 수평으로 배치하는 레이아웃
    QTextEdit,  # 여러 줄의 텍스트를 표시하고 편집하는 위젯
    QGridLayout,  # 위젯을 그리드(격자) 형태로 배치하는 레이아웃
    QGroupBox,  # 다른 위젯들을 그룹화하고 제목을 표시하는 컨테이너
    QPushButton,  # 클릭 가능한 버튼
    QProgressBar,  # 작업 진행 상태를 보여주는 바
    QButtonGroup,  # 여러 버튼을 그룹으로 묶어 관리 (주로 라디오 버튼처럼 하나만 선택되도록 할 때 사용)
    QLabel,  # 텍스트나 이미지를 표시하는 라벨
)

# logger.py 파일에서 QtLogHandler 클래스를 가져옵니다.
# 이 핸들러는 로그 메시지를 PyQt 시그널로 보내는 역할을 합니다.
from logger import QtLogHandler


class View(QMainWindow):
    """
    애플리케이션의 사용자 인터페이스(UI)를 생성하고 관리하는 메인 윈도우 클래스입니다.
    QMainWindow를 상속받아 메뉴바, 툴바, 상태바 등을 사용할 수 있는 기본 창 구조를 가집니다.
    """

    # pyqtSignal(object): '시작' 버튼 클릭 시 Controller에 사용자 선택 옵션(Options 객체)을 전달할 시그널
    start_clicked = pyqtSignal(object)
    # pyqtSignal(): '중지' 버튼 클릭 시 Controller에 알릴 시그널
    stop_clicked = pyqtSignal()

    def __init__(self):
        """View 클래스의 생성자(initializer)입니다."""
        # 부모 클래스인 QMainWindow의 생성자를 호출합니다.
        super().__init__()
        # 창의 제목을 "Kdic Setup v. 2.0"으로 설정합니다.
        self.setWindowTitle("Kdic Setup v. 2.0")
        # 창의 크기와 화면 중앙 위치를 설정하는 내부 메서드를 호출합니다.
        self._set_window_size_and_position(640, 480)

        # 메인 윈도우의 중앙에 위치할 위젯을 생성합니다.
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        # 중앙 위젯에 적용될 메인 수직 레이아웃을 생성합니다.
        main_layout = QVBoxLayout(central_widget)

        # 상단 로그 뷰어를 생성하고 초기 안내 문구를 설정합니다.
        self.log_viewer_top = self._create_log_viewer(
            "시스템 분석중입니다. 잠시만 기다려주세요."
        )
        # 하단 설명 뷰어를 생성하고 초기 안내 문구를 설정합니다.
        self.log_viewer_bottom = self._create_log_viewer(
            "타입을 선택하면 여기에 설명이 표시됩니다."
        )
        # PC 타입을 선택하는 버튼 그룹을 생성합니다.
        self.types_group = self._create_types_group()
        # 하단 버튼 및 프로그레스 바가 포함된 레이아웃을 생성합니다.
        bottom_layout = self._create_bottom_layout()

        # 메인 레이아웃에 생성된 위젯과 레이아웃을 순서대로 추가합니다.
        # addWidget(위젯, stretch_factor): stretch_factor는 레이아웃 내에서 위젯이 차지하는 공간의 비율을 조절합니다.
        main_layout.addWidget(
            self.log_viewer_top, 2
        )  # 상단 로그 뷰어가 2의 비율로 공간 차지
        main_layout.addWidget(
            self.log_viewer_bottom, 1
        )  # 하단 설명 뷰어가 1의 비율로 공간 차지
        main_layout.addWidget(self.types_group)
        main_layout.addLayout(bottom_layout)

        # 타입 선택 버튼 그룹에서 버튼이 클릭될 때 _update_bitlocker_button_state 메서드가 호출되도록 연결합니다.
        self.types_button_group.buttonClicked.connect(
            self._update_bitlocker_button_state
        )
        # QtLogHandler 인스턴스를 생성하여 로깅 시스템과 UI를 연결합니다.
        self.log_handler = QtLogHandler()
        # 로그 핸들러에서 log_received 시그널이 발생하면, 그 메시지를 상단 로그 뷰어에 추가(append)하도록 연결합니다.
        self.log_handler.log_received.connect(self.log_viewer_top.append)

    def _set_window_size_and_position(self, width: int, height: int):
        """창의 크기를 설정하고 화면의 중앙에 위치시키는 메서드입니다."""
        # 창의 너비와 높이를 설정합니다.
        self.resize(width, height)
        # 주 화면(primary screen)의 정보를 가져옵니다.
        screen = QApplication.primaryScreen()
        if screen:
            # 화면의 중앙 좌표를 계산합니다.
            center_point = screen.geometry().center()
            # 창의 좌측 상단 좌표를 (화면 중앙 X - 창 너비의 절반, 화면 중앙 Y - 창 높이의 절반)으로 이동시킵니다.
            self.move(center_point.x() - width // 2, center_point.y() - height // 2)

    def _create_log_viewer(self, placeholder: str) -> QTextEdit:
        """읽기 전용 QTextEdit 위젯을 생성하고 초기 안내 문구(placeholder)를 설정합니다."""
        log_viewer = QTextEdit()
        # 사용자가 텍스트를 편집할 수 없도록 읽기 전용으로 설정합니다.
        log_viewer.setReadOnly(True)
        # 위젯이 비어 있을 때 표시될 안내 텍스트를 설정합니다.
        log_viewer.setPlaceholderText(placeholder)
        return log_viewer

    def _create_types_group(self) -> QGroupBox:
        """PC 타입을 선택하는 버튼들을 담는 그룹박스를 생성합니다."""
        group_box = QGroupBox("타입 선택")
        # 그룹박스 안에 위젯들을 격자 형태로 배치할 QGridLayout을 생성합니다.
        grid_layout = QGridLayout(group_box)
        # 버튼 ID와 텍스트를 딕셔너리로 정의합니다.
        buttons = {0: "내부망", 1: "인터넷", 2: "출장용", 3: "K자회사"}
        # 버튼들을 관리할 QButtonGroup을 생성합니다.
        self.types_button_group = QButtonGroup(self)
        # setExclusive(True): 그룹 내에서 오직 하나의 버튼만 선택(checked)될 수 있도록 설정합니다.
        self.types_button_group.setExclusive(True)

        # 딕셔너리의 아이템들을 순회하며 버튼을 생성하고 그리드 레이아웃에 추가합니다.
        for i, text in buttons.items():
            button = QPushButton(text)
            # setCheckable(True): 버튼이 눌린 상태를 유지할 수 있도록(토글 버튼처럼) 설정합니다.
            button.setCheckable(True)
            # 버튼 그룹에 버튼을 추가하고, 고유한 ID(i)를 할당합니다.
            self.types_button_group.addButton(button, i)
            # divmod(i, 2): i를 2로 나눈 몫(row)과 나머지(col)를 계산하여 2열 그리드에 배치합니다.
            row, col = divmod(i, 2)
            grid_layout.addWidget(button, row, col)

        return group_box

    def _create_bottom_layout(self) -> QVBoxLayout:
        """화면 하단의 버튼들과 프로그레스 바를 포함하는 레이아웃을 생성합니다."""
        bottom_layout = QVBoxLayout()

        # '데이터 보존' 버튼 생성
        self.data_save_button = QPushButton("데이터 보존")
        self.data_save_button.setCheckable(True)  # 토글 기능 활성화
        self.data_save_button.setEnabled(False)  # 초기에는 비활성화 상태

        # 'BitLocker 설정' 버튼 생성
        self.bitlocker_button = QPushButton("BitLocker 설정")
        self.bitlocker_button.setCheckable(True)  # 토글 기능 활성화
        self.bitlocker_button.setEnabled(False)  # 초기에는 비활성화 상태

        # '시작'/'중지' 버튼 생성
        self.start_stop_button = QPushButton("시작")
        self.start_stop_button.setCheckable(True)  # 토글 기능 활성화
        self.start_stop_button.setEnabled(False)  # 초기에는 비활성화 상태

        # 생성된 버튼들을 수직 레이아웃에 추가합니다.
        bottom_layout.addWidget(self.data_save_button)
        bottom_layout.addWidget(self.bitlocker_button)
        bottom_layout.addWidget(self.start_stop_button)

        # 프로그레스 바와 남은 시간 라벨을 담을 수평 레이아웃을 생성합니다.
        progress_layout = QHBoxLayout()
        # 프로그레스 바 생성
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)  # 초기 진행률을 0으로 설정
        # 남은 시간 라벨 생성
        self.time_label = QLabel("예상 남은 시간: -")
        self.time_label.setFixedWidth(150)  # 라벨의 너비를 150px로 고정
        # 수평 레이아웃에 프로그레스 바와 라벨을 추가합니다.
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.time_label)
        # 메인 수직 레이아웃에 프로그레스 바 레이아웃을 추가합니다.
        bottom_layout.addLayout(progress_layout)

        return bottom_layout

    def set_data_save_enabled(self, enabled: bool):
        """'데이터 보존' 버튼의 활성화/비활성화 상태를 설정하는 메서드입니다."""
        self.data_save_button.setEnabled(enabled)
        # 활성화될 경우, 기본적으로 선택된 상태(checked)로 만듭니다.
        self.data_save_button.setChecked(enabled)

    def _update_bitlocker_button_state(self):
        """'출장용' 타입이 선택되었는지 여부에 따라 'BitLocker 설정' 버튼의 상태를 업데이트합니다."""
        # 현재 선택된 버튼의 ID가 2('출장용')인지 확인합니다.
        is_trip_options = self.types_button_group.checkedId() == 2
        # '출장용'일 경우에만 BitLocker 버튼을 활성화하고 선택 상태로 만듭니다.
        self.bitlocker_button.setEnabled(is_trip_options)
        self.bitlocker_button.setChecked(is_trip_options)

    def set_ui_for_loading(self, is_loading: bool):
        """시스템 분석(로딩) 중일 때와 아닐 때의 UI 상태를 설정합니다."""
        interactive = not is_loading  # 로딩 중이 아닐 때만 상호작용 가능
        self.types_group.setEnabled(interactive)
        self.start_stop_button.setEnabled(interactive)
        # 로딩 중에는 데이터 보존 및 BitLocker 옵션을 비활성화하고 선택 해제합니다.
        self.data_save_button.setEnabled(False)
        self.data_save_button.setChecked(False)
        if not is_loading:
            # 로딩이 끝나면 BitLocker 버튼 상태를 다시 업데이트합니다.
            self._update_bitlocker_button_state()
        else:
            self.bitlocker_button.setEnabled(False)
            self.bitlocker_button.setChecked(False)
        # 로딩 중일 때는 프로그레스 바가 계속 움직이는 'indeterminate' 상태로 만듭니다.
        self.set_progress_bar_infinite(is_loading)

    def set_ui_for_task_running(self, is_running: bool):
        """자동화 작업이 실행 중일 때와 아닐 때의 UI 상태를 설정합니다."""
        interactive = not is_running  # 작업 실행 중이 아닐 때만 상호작용 가능
        self.types_group.setEnabled(interactive)
        self.data_save_button.setEnabled(interactive)
        self.bitlocker_button.setEnabled(interactive)
        if not is_running:
            # 작업이 끝나면 BitLocker 및 데이터 보존 버튼 상태를 초기화/업데이트합니다.
            self._update_bitlocker_button_state()
            self.data_save_button.setEnabled(False)
            self.data_save_button.setChecked(False)
        # 작업 실행 여부에 따라 '시작'/'중지' 버튼의 텍스트와 선택 상태를 변경합니다.
        self.start_stop_button.setText("중지" if is_running else "시작")
        self.start_stop_button.setChecked(is_running)

    def set_progress_bar_infinite(self, active: bool):
        """프로그레스 바를 'indeterminate'(계속 움직이는) 모드로 설정하거나 해제합니다."""
        if active:
            # 범위를 (0, 0)으로 설정하면 indeterminate 모드가 됩니다.
            self.progress_bar.setRange(0, 0)
        else:
            # 범위를 (0, 100)으로 설정하여 일반적인 진행률 표시 모드로 되돌립니다.
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)  # 진행률을 0으로 초기화

    def update_time_label(self, time_str: str):
        """(Controller용) 예상 남은 시간 라벨의 텍스트를 업데이트합니다."""
        self.time_label.setText(f"예상 남은 시간: {time_str}")
