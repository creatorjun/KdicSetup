# logger.py

# logging 모듈: 프로그램의 이벤트 기록(로깅)을 위한 표준 라이브러리입니다.
import logging

# functools 모듈: 고차 함수(함수를 인자로 받거나 반환하는 함수)를 다루는 유틸리티를 제공합니다.
# 데코레이터를 만들 때 원본 함수의 메타데이터(이름, 독스트링 등)를 보존하기 위해 사용됩니다.
import functools

# PyQt6.QtCore 모듈: Qt의 핵심 비-GUI 기능을 제공합니다.
# QObject: Qt의 모든 객체의 기본 클래스로, 시그널/슬롯 메커니즘을 제공합니다.
# pyqtSignal: 사용자 정의 시그널을 생성하는 데 사용됩니다.
from PyQt6.QtCore import QObject, pyqtSignal

# ==============================================================================
# 1. 사용자 정의 레벨 및 핸들러
# ==============================================================================

# USER_LOG_LEVEL: 사용자에게 직접 보여줄 로그 메시지를 위한 커스텀 로그 레벨을 정의합니다.
# 기본 레벨(INFO=20, WARNING=30) 사이에 새로운 레벨을 추가합니다.
USER_LOG_LEVEL = 25
# logging 모듈에 새로운 로그 레벨 이름('USER')과 레벨 번호(25)를 등록합니다.
logging.addLevelName(USER_LOG_LEVEL, "USER")


class QtLogHandler(logging.Handler, QObject):
    """
    logging.Handler를 상속받아 로그 레코드를 처리하고,
    QObject를 상속받아 처리된 로그 메시지를 PyQt 시그널로 보내는 커스텀 핸들러입니다.
    이를 통해 백그라운드 스레드의 로그를 메인 UI 스레드로 안전하게 전달할 수 있습니다.
    """

    # 로그 메시지를 문자열 형태로 전달하는 'log_received'라는 이름의 시그널을 정의합니다.
    log_received = pyqtSignal(str)

    def __init__(self):
        # 부모 클래스(logging.Handler, QObject)의 초기화 메서드를 순서대로 호출합니다.
        super().__init__()
        QObject.__init__(self)

    def emit(self, record):
        """
        로거가 로그를 생성할 때마다 호출되는 메서드입니다.
        로그 레코드(record)를 포매터에 따라 문자열로 변환하고 시그널을 발생시킵니다.
        """
        # self.format(record)를 통해 로그 레코드를 포맷에 맞는 문자열로 만듭니다.
        msg = self.format(record)
        # log_received 시그널에 포맷된 메시지를 담아 발생(emit)시킵니다.
        # 이 시그널에 연결된 슬롯(예: view.py의 QTextEdit.append)이 메시지를 받아 처리하게 됩니다.
        self.log_received.emit(msg)


# ==============================================================================
# 2. 로깅 데코레이터
# ==============================================================================


def log_function_call(func):
    """
    함수의 시작, 종료, 예외 발생을 자동으로 로깅하는 데코레이터입니다.
    이 데코레이터를 함수 위에 @log_function_call 형태로 붙이면,
    해당 함수가 호출될 때마다 관련 정보가 로그 파일에 기록됩니다.
    """

    # @functools.wraps(func): 데코레이터가 적용된 함수의 원본 메타데이터(이름, 독스트링 등)를 유지시킵니다.
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        """데코레이터의 실제 동작을 감싸는 래퍼 함수입니다."""
        # args[1:]: self 인자를 제외한 위치 인자들을 문자열로 변환합니다.
        args_repr = [repr(a) for a in args[1:]]
        # 키워드 인자들을 'key=value' 형태의 문자열로 변환합니다.
        kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
        # 위치 인자와 키워드 인자 문자열을 합쳐 함수의 시그니처 문자열을 생성합니다.
        signature = ", ".join(args_repr + kwargs_repr)

        # 로거를 가져옵니다. __module__은 함수가 정의된 모듈의 이름을 나타냅니다.
        logger = logging.getLogger(func.__module__)
        # 함수 호출 시작을 INFO 레벨로 로깅합니다.
        logger.info(f"호출 시작: {func.__name__}({signature})")
        try:
            # 원본 함수를 실행하고 그 결과를 result 변수에 저장합니다.
            result = func(*args, **kwargs)
            # 함수 호출이 성공적으로 종료되었음을 INFO 레벨로 로깅합니다.
            logger.info(f"호출 종료: {func.__name__} -> {result!r}")
            # 원본 함수의 반환값을 그대로 반환합니다.
            return result
        except Exception as e:
            # 함수 실행 중 예외가 발생하면, 예외 정보를 EXCEPTION 레벨로 로깅합니다.
            # logger.exception은 오류 메시지와 함께 스택 트레이스 정보도 기록합니다.
            logger.exception(f"{func.__name__} 실행 중 예외 발생: {e}")
            # 발생한 예외를 다시 발생시켜 프로그램의 정상적인 예외 처리 흐름을 방해하지 않습니다.
            raise

    # 래퍼 함수를 반환합니다.
    return wrapper


# ==============================================================================
# 3. 로깅 시스템 설정 함수
# ==============================================================================


def setup_logging(gui_handler: QtLogHandler):
    """
    애플리케이션의 전역 로깅 시스템을 설정합니다.
    GUI 표시용, 파일 저장용 등 여러 핸들러를 설정하고 각 핸들러의 포맷과 레벨을 지정합니다.
    """
    # user_formatter: GUI에 표시될 로그 메시지의 포맷입니다. 메시지 내용만 간결하게 보여줍니다.
    user_formatter = logging.Formatter("%(message)s")
    # dev_formatter: log.txt 파일에 저장될 로그 메시지의 포맷입니다.
    # 시간, 로그 레벨, 로거 이름, 메시지 등 상세 정보를 포함합니다.
    dev_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
    )

    # 루트 로거를 가져옵니다. 모든 로거의 최상위 로거입니다.
    root_logger = logging.getLogger()
    # 루트 로거의 레벨을 INFO로 설정합니다. INFO 레벨 이상의 모든 로그가 처리됩니다.
    root_logger.setLevel(logging.INFO)

    # GUI 핸들러의 레벨을 USER_LOG_LEVEL로 설정합니다.
    # 즉, logging.log(USER_LOG_LEVEL, "메시지") 형태로 호출된 로그만 이 핸들러가 처리합니다.
    gui_handler.setLevel(USER_LOG_LEVEL)
    # GUI 핸들러에 사용자용 포매터를 적용합니다.
    gui_handler.setFormatter(user_formatter)
    # 루트 로거에 GUI 핸들러를 추가합니다.
    root_logger.addHandler(gui_handler)

    try:
        # 파일 핸들러를 생성합니다. 'log.txt' 파일에 로그를 기록하며, 매 실행 시 덮어씁니다(mode='w').
        file_handler = logging.FileHandler("log.txt", mode="w", encoding="utf-8")
        # 파일 핸들러의 레벨을 INFO로 설정합니다. INFO 레벨 이상의 모든 로그가 파일에 기록됩니다.
        file_handler.setLevel(logging.INFO)
        # 파일 핸들러에 개발자용 포매터를 적용합니다.
        file_handler.setFormatter(dev_formatter)
        # 루트 로거에 파일 핸들러를 추가합니다.
        root_logger.addHandler(file_handler)
    except PermissionError:
        # 권한 문제로 로그 파일을 생성할 수 없을 경우, 경고 메시지를 로깅합니다.
        logging.warning("log.txt 파일을 생성할 수 없어 파일 로그를 기록할 수 없습니다.")

    # 로깅 시스템 설정이 완료되었음을 알리는 로그를 기록합니다.
    logging.info("로깅 시스템이 시작되었습니다.")
