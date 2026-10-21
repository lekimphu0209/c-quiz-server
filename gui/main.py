import sys
from dataclasses import dataclass, field
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QStackedWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox,
)
from state import AppState
from styles import DARK_STYLE
from net import NetThread
from screens import (
    LoginScreen,
    DashboardScreen,
    LobbyScreen,
    WaitingScreen,
    ExamScreen,
    ResultScreen,
    HistoryScreen,
    AdminScreen,
)


class MainWindow(QMainWindow):
    """Main window hosting the QStackedWidget screen navigation."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hệ Thống Thi Trắc Nghiệm Trực Tuyến — Client GUI")
        self.resize(1050, 720)
        self.setMinimumSize(850, 600)

        self.app_state = AppState()
        self.net = NetThread()

        # Connect NetThread signals
        self.net.response.connect(self.route_response)
        self.net.event.connect(self.route_event)
        self.net.disconnected.connect(self.on_disconnected)

        self._init_ui()

    def _init_ui(self):
        container = QWidget()
        self.main_layout = QVBoxLayout(container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Disconnection banner (hidden by default)
        self.banner = QWidget()
        self.banner.setStyleSheet("background-color: #dc2626; color: white; padding: 6px;")
        b_layout = QHBoxLayout(self.banner)
        b_layout.setContentsMargins(16, 4, 16, 4)

        self.lbl_banner = QLabel("⚠️ Mất kết nối tới máy chủ! Vui lòng đăng nhập lại để tiếp tục.")
        self.lbl_banner.setStyleSheet("font-weight: 700; color: white;")

        self.btn_reconnect = QPushButton("Kết nối lại")
        self.btn_reconnect.setStyleSheet(
            "background-color: white; color: #dc2626; font-weight: 800; border-radius: 4px; padding: 4px 10px;"
        )
        self.btn_reconnect.clicked.connect(self.do_reconnect)

        b_layout.addWidget(self.lbl_banner)
        b_layout.addStretch()
        b_layout.addWidget(self.btn_reconnect)
        self.banner.setVisible(False)
        self.main_layout.addWidget(self.banner)

        # Stacked Screens Container
        self.stack = QStackedWidget()
        self.screens = {
            "login": LoginScreen(self.app_state, self.net, self.goto),
            "dashboard": DashboardScreen(self.app_state, self.net, self.goto),
            "lobby": LobbyScreen(self.app_state, self.net, self.goto),
            "waiting": WaitingScreen(self.app_state, self.net, self.goto),
            "exam": ExamScreen(self.app_state, self.net, self.goto),
            "result": ResultScreen(self.app_state, self.net, self.goto),
            "history": HistoryScreen(self.app_state, self.net, self.goto),
            "admin": AdminScreen(self.app_state, self.net, self.goto),
        }

        for name, screen in self.screens.items():
            self.stack.addWidget(screen)

        self.main_layout.addWidget(self.stack)
        self.setCentralWidget(container)

        self.current_name = "login"
        self.goto("login")

    def goto(self, name: str):
        if name not in self.screens:
            return

        cur_widget = self.stack.currentWidget()
        if cur_widget and hasattr(cur_widget, "on_leave"):
            cur_widget.on_leave()

        target_widget = self.screens[name]
        self.current_name = name
        self.stack.setCurrentWidget(target_widget)

        if hasattr(target_widget, "on_enter"):
            target_widget.on_enter()

    def route_response(self, payload: str):
        cur_widget = self.stack.currentWidget()
        if cur_widget and hasattr(cur_widget, "on_response"):
            cur_widget.on_response(payload)

    def route_event(self, payload: str):
        parts = payload.split("|")
        if len(parts) < 2:
            return

        evt_type = parts[1]
        cur_widget = self.stack.currentWidget()

        if evt_type == "RESULT":
            if self.current_name == "exam":
                cur_widget.handle_event(payload)
            else:
                rid = parts[2] if len(parts) > 2 else ""
                score_str = parts[3] if len(parts) > 3 else ""
                self.statusBar().showMessage(f"🔔 Phòng #{rid} vừa kết thúc! Điểm: {score_str}", 6000)

        elif evt_type in ("MEMBER_JOINED", "MEMBER_LEFT", "ROOM_CLOSED", "EXAM"):
            if self.current_name == "waiting":
                cur_widget.handle_event(payload)

        elif evt_type == "TICK":
            if self.current_name == "exam":
                cur_widget.handle_event(payload)

    def on_disconnected(self):
        self.banner.setVisible(True)
        if self.current_name == "exam":
            QMessageBox.warning(
                self,
                "Mất kết nối mạng",
                "Mất kết nối tới server trong khi đang làm bài thi!\n"
                "Tiến trình của bạn đã được lưu lại trên server.\n"
                "Vui lòng đăng nhập lại để tiếp tục bài thi (RESUME).",
            )
        self.goto("login")

    def do_reconnect(self):
        self.banner.setVisible(False)
        self.goto("login")

    def closeEvent(self, event):
        if self.current_name == "exam":
            reply = QMessageBox.question(
                self,
                "Xác nhận thoát",
                "Bạn đang trong bài thi. Thoát ứng dụng sẽ không hủy bài thi của bạn và hệ thống vẫn chấm điểm khi hết giờ.\n"
                "Bạn có chắc chắn muốn thoát?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                event.ignore()
                return

        self.net.disconnect()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
