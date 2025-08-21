import sys
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from logger import setup_logging
from view import View
from controller import Controller

# --- 추가된 부분: 빠른 편집 모드 비활성화 ---
import ctypes

def disable_quick_edit_mode():
    """
    Windows 콘솔의 빠른 편집 모드를 비활성화하여
    자동화 스크립트가 멈추는 현상을 방지합니다.
    """
    if sys.platform != "win32":
        return # Windows가 아닌 환경에서는 실행하지 않음

    try:
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        # 빠른 편집 모드 비활성화를 위한 상수
        ENABLE_QUICK_EDIT_MODE = 0x0040
        STD_INPUT_HANDLE = -10
        
        device = kernel32.GetStdHandle(STD_INPUT_HANDLE)
        
        # 현재 콘솔 모드를 가져옴
        mode = ctypes.c_uint32()
        kernel32.GetConsoleMode(device, ctypes.byref(mode))
        
        # 빠른 편집 모드 플래그를 제거하고 새로운 모드를 설정
        new_mode = mode.value & ~ENABLE_QUICK_EDIT_MODE
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
    """
    traceback_details = "".join(traceback.format_exception(exctype, value, tb))
    error_msg = (
        f"예기치 않은 오류가 발생하여 프로그램을 종료해야 합니다.\n\n"
        f"오류 정보:\n{traceback_details}"
    )
    _ = QApplication.instance() or QApplication([])
    QMessageBox.critical(None, "치명적 오류 발생", error_msg)
    sys.exit(1)


def main():
    """애플리케이션의 진입점(entry point) 함수."""
    # --- 추가된 부분: 프로그램 시작 시 빠른 편집 모드 비활성화 함수 호출 ---
    disable_quick_edit_mode()

    sys.excepthook = global_exception_hook

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("icon/kdic.ico"))

    view = View()
    setup_logging(gui_handler=view.log_handler)

    controller = Controller(view)
    view.show()
    controller.start_loading()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()