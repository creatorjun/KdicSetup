# main.py

import sys
from PyQt5.QtWidgets import QApplication

# view.py 파일에서 View 클래스를 가져옴
from view import View

if __name__ == "__main__":
    app = QApplication(sys.argv)
    view = View()
    view.show()
    sys.exit(app.exec_())