import logging
import functools
from PyQt6.QtCore import QObject, pyqtSignal

# ==============================================================================
# 1. 사용자 정의 레벨 및 핸들러
# ==============================================================================

USER_LOG_LEVEL = 25
logging.addLevelName(USER_LOG_LEVEL, "USER")


class QtLogHandler(logging.Handler, QObject):
    log_received = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        QObject.__init__(self)

    def emit(self, record):
        msg = self.format(record)
        self.log_received.emit(msg)


# ==============================================================================
# 2. 로깅 데코레이터
# ==============================================================================


def log_function_call(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        args_repr = [repr(a) for a in args[1:]]
        kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
        signature = ", ".join(args_repr + kwargs_repr)
        logger = logging.getLogger(func.__module__)
        logger.info(f"호출 시작: {func.__name__}({signature})")
        try:
            result = func(*args, **kwargs)
            logger.info(f"호출 종료: {func.__name__} -> {result!r}")
            return result
        except Exception as e:
            logger.exception(f"{func.__name__} 실행 중 예외 발생: {e}")
            raise

    return wrapper


# ==============================================================================
# 3. 로깅 시스템 설정 함수
# ==============================================================================


def setup_logging(gui_handler: QtLogHandler):
    user_formatter = logging.Formatter("%(message)s")
    dev_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    gui_handler.setLevel(USER_LOG_LEVEL)
    gui_handler.setFormatter(user_formatter)
    root_logger.addHandler(gui_handler)

    try:
        file_handler = logging.FileHandler(
            "log.txt", mode='w', encoding="utf-8"
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(dev_formatter)
        root_logger.addHandler(file_handler)
    except PermissionError:
        logging.warning("log.txt 파일을 생성할 수 없어 파일 로그를 기록할 수 없습니다.")

    logging.info("로깅 시스템이 시작되었습니다.")
