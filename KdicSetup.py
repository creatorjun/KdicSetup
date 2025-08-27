# KdicSetup.py

# sys 모듈: 파이썬 인터프리터가 제공하는 변수와 함수를 직접 제어할 수 있게 해줍니다.
# traceback 모듈: 프로그램 실행 중 발생한 오류의 트레이스백 정보를 추출하고 형식화하는 기능을 제공합니다.
import sys
import traceback

# PyQt6.QtWidgets 모듈: GUI 애플리케이션을 만드는 데 필요한 위젯들을 포함합니다.
# QApplication: GUI 애플리케이션의 실행을 관리하는 클래스입니다.
# QMessageBox: 사용자에게 정보, 경고, 오류 등을 알리는 대화상자를 생성하는 클래스입니다.
from PyQt6.QtWidgets import QApplication, QMessageBox

# PyQt6.QtGui 모듈: GUI 애플리케이션의 아이콘, 글꼴, 색상 등 그래픽 관련 기능을 다룹니다.
# QIcon: 애플리케이션 창이나 버튼 등에 사용될 아이콘을 관리하는 클래스입니다.
from PyQt6.QtGui import QIcon

# logger.py 파일에서 로깅 시스템 설정을 위한 setup_logging 함수를 가져옵니다.
from logger import setup_logging

# view.py 파일에서 UI를 정의하는 View 클래스를 가져옵니다.
from view import View

# controller.py 파일에서 애플리케이션의 메인 로직을 담당하는 Controller 클래스를 가져옵니다.
from controller import Controller

# --- 추가된 부분: 빠른 편집 모드 비활성화 ---
# ctypes 모듈: C 데이터 타입을 지원하며, DLL이나 공유 라이브러리의 함수를 호출할 수 있게 해줍니다.
# Windows API를 직접 호출하기 위해 사용됩니다.
import ctypes


def disable_quick_edit_mode():
    """
    Windows 콘솔의 빠른 편집 모드를 비활성화하여
    자동화 스크립트가 멈추는 현상을 방지합니다.
    """
    # 현재 운영체제가 'win32' (Windows)가 아니면 함수를 종료합니다.
    if sys.platform != "win32":
        return  # Windows가 아닌 환경에서는 실행하지 않음

    try:
        # kernel32.dll을 로드하여 Windows API 함수를 사용할 수 있도록 합니다.
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        # Windows API에서 사용되는 상수 정의
        ENABLE_QUICK_EDIT_MODE = 0x0040  # 빠른 편집 모드를 제어하는 플래그
        STD_INPUT_HANDLE = -10  # 표준 입력 핸들을 가리키는 상수

        # 표준 입력 장치에 대한 핸들(식별자)을 가져옵니다.
        device = kernel32.GetStdHandle(STD_INPUT_HANDLE)

        # 현재 콘솔의 모드(설정 상태)를 저장할 변수를 생성합니다.
        mode = ctypes.c_uint32()
        # GetConsoleMode 함수를 호출하여 현재 콘솔 모드를 'mode' 변수에 저장합니다.
        kernel32.GetConsoleMode(device, ctypes.byref(mode))

        # 비트 연산(& ~)을 사용하여 현재 모드에서 빠른 편집 모드 플래그만 제거합니다.
        new_mode = mode.value & ~ENABLE_QUICK_EDIT_MODE
        # SetConsoleMode 함수를 호출하여 빠른 편집 모드가 비활성화된 새 모드를 콘솔에 적용합니다.
        kernel32.SetConsoleMode(device, new_mode)

        print("빠른 편집 모드가 성공적으로 비활성화되었습니다.")
    except Exception as e:
        # 이 코드가 GUI 환경이나 IDE의 내장 터미널에서 실행되면
        # 콘솔 핸들을 얻지 못해 오류가 발생할 수 있습니다.
        # 실제 배포 환경에서는 문제가 되지 않으므로 경고만 출력합니다.
        print(f"경고: 빠른 편집 모드를 비활성화할 수 없습니다. {e}")


# --- 기존 전역 예외 처리기 ---
def global_exception_hook(exctype, value, tb):
    """
    처리되지 않은 모든 예외를 잡아 사용자에게 팝업으로 보여주는 함수.
    이 함수는 프로그램 전체에서 발생하는 예외를 일관되게 처리하기 위해 사용됩니다.
    """
    # 예외 타입, 값, 트레이스백 정보를 문자열로 변환합니다.
    traceback_details = "".join(traceback.format_exception(exctype, value, tb))
    # 사용자에게 보여줄 오류 메시지를 생성합니다.
    error_msg = (
        f"예기치 않은 오류가 발생하여 프로그램을 종료해야 합니다.\n\n"
        f"오류 정보:\n{traceback_details}"
    )
    # QApplication 인스턴스가 없으면 새로 생성합니다. 이는 GUI가 아직 시작되지 않았을 때를 대비합니다.
    _ = QApplication.instance() or QApplication([])
    # 치명적 오류임을 알리는 메시지 상자를 표시합니다.
    QMessageBox.critical(None, "치명적 오류 발생", error_msg)
    # 프로그램을 종료합니다. 상태 코드 1은 비정상 종료를 의미합니다.
    sys.exit(1)


def main():
    """애플리케이션의 진입점(entry point) 함수."""
    # --- 추가된 부분: 프로그램 시작 시 빠른 편집 모드 비활성화 함수 호출 ---
    disable_quick_edit_mode()

    # 파이썬의 기본 예외 처리기를 우리가 만든 global_exception_hook 함수로 교체합니다.
    sys.excepthook = global_exception_hook

    # QApplication 객체를 생성합니다. 모든 PyQt GUI 애플리케이션은 이 객체가 필요합니다.
    app = QApplication(sys.argv)
    # 애플리케이션 창의 아이콘을 설정합니다.
    app.setWindowIcon(QIcon("icon/kdic.ico"))

    # View 클래스의 인스턴스를 생성하여 UI를 만듭니다.
    view = View()
    # 로깅 시스템을 설정하고, 로그 메시지를 GUI에 표시할 핸들러를 전달합니다.
    setup_logging(gui_handler=view.log_handler)

    # Controller 클래스의 인스턴스를 생성하고 View 객체를 전달하여 UI와 로직을 연결합니다.
    controller = Controller(view)
    # UI 창을 화면에 표시합니다.
    view.show()
    # 컨트롤러를 통해 시스템 분석(로딩) 작업을 시작합니다.
    controller.start_loading()

    # 애플리케이션의 이벤트 루프를 시작합니다. 사용자의 입력을 받고 처리하며, 창이 닫힐 때까지 실행됩니다.
    # app.exec()의 반환값으로 프로그램을 종료합니다.
    sys.exit(app.exec())


# 이 스크립트 파일이 직접 실행될 때만 main() 함수를 호출합니다.
# 다른 모듈에서 이 파일을 import할 경우에는 main() 함수가 실행되지 않습니다.
if __name__ == "__main__":
    main()
