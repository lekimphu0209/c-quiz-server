import os
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QMessageBox,
)
from proto import build_cmd, parse_err


class LoginScreen(QWidget):
    def __init__(self, app_state, net, goto_callback, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.net = net
        self.goto = goto_callback
        self.pending_cmd = None
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        # Central Card Container
        card = QFrame()
        card.setProperty("card", "true")
        card.setFixedWidth(420)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)
        card_layout.setContentsMargins(32, 32, 32, 32)

        # Title / Branding
        lbl_title = QLabel("C-QUIZ SYSTEM")
        lbl_title.setProperty("heading", "true")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("font-size: 24px; font-weight: 900; color: #818cf8; letter-spacing: 1px;")

        lbl_subtitle = QLabel("Hệ thống thi trắc nghiệm trực tuyến")
        lbl_subtitle.setProperty("subheading", "true")
        lbl_subtitle.setAlignment(Qt.AlignCenter)

        # Server Settings Row
        conn_row = QHBoxLayout()
        self.ed_ip = QLineEdit(os.environ.get("SERVER_HOST", "127.0.0.1"))
        self.ed_ip.setPlaceholderText("Server IP")
        self.ed_port = QLineEdit(os.environ.get("SERVER_PORT", "5000"))
        self.ed_port.setPlaceholderText("Port")
        self.ed_port.setFixedWidth(80)

        conn_row.addWidget(self.ed_ip)
        conn_row.addWidget(self.ed_port)

        # Inputs
        self.ed_user = QLineEdit()
        self.ed_user.setPlaceholderText("Tên đăng nhập (3-20 ký tự)")
        self.ed_user.returnPressed.connect(lambda: self.ed_pass.setFocus())

        self.ed_pass = QLineEdit()
        self.ed_pass.setPlaceholderText("Mật khẩu (tối thiểu 6 ký tự)")
        self.ed_pass.setEchoMode(QLineEdit.Password)
        self.ed_pass.returnPressed.connect(self.do_login)

        # Buttons Row
        btn_layout = QHBoxLayout()
        self.btn_login = QPushButton("ĐĂNG NHẬP")
        self.btn_login.clicked.connect(self.do_login)

        self.btn_register = QPushButton("ĐĂNG KÝ")
        self.btn_register.setProperty("secondary", "true")
        self.btn_register.clicked.connect(self.do_register)

        btn_layout.addWidget(self.btn_login)
        btn_layout.addWidget(self.btn_register)

        # Status & Error
        self.lbl_status = QLabel("○ Chưa kết nối")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("color: #94a3b8; font-size: 12px;")

        self.lbl_error = QLabel("")
        self.lbl_error.setProperty("error", "true")
        self.lbl_error.setAlignment(Qt.AlignCenter)
        self.lbl_error.setWordWrap(True)
        self.lbl_error.hide()

        # Assemble card
        card_layout.addWidget(lbl_title)
        card_layout.addWidget(lbl_subtitle)
        card_layout.addSpacing(10)
        card_layout.addLayout(conn_row)
        card_layout.addWidget(self.ed_user)
        card_layout.addWidget(self.ed_pass)
        card_layout.addLayout(btn_layout)
        card_layout.addWidget(self.lbl_error)
        card_layout.addWidget(self.lbl_status)

        main_layout.addWidget(card)

    def on_enter(self):
        self.lbl_error.hide()
        self.ed_pass.clear()
        self.pending_cmd = None
        self.update_connection_status()

    def on_leave(self):
        self.pending_cmd = None

    def update_connection_status(self):
        if self.net.is_connected():
            self.lbl_status.setText("● Đã kết nối")
            self.lbl_status.setStyleSheet("color: #10b981; font-weight: 700; font-size: 12px;")
        else:
            self.lbl_status.setText("○ Chưa kết nối")
            self.lbl_status.setStyleSheet("color: #94a3b8; font-size: 12px;")

    def _ensure_connection(self) -> bool:
        if not self.net.is_connected():
            host = self.ed_ip.text().strip() or "127.0.0.1"
            port = self.ed_port.text().strip() or "5000"
            if not self.net.connect_server(host, port):
                self.show_error("Không thể kết nối tới server. Vui lòng kiểm tra IP và Port.")
                return False
        self.update_connection_status()
        return True

    def show_error(self, message: str):
        self.lbl_error.setText(message)
        self.lbl_error.show()

    def do_login(self):
        self.lbl_error.hide()
        u = self.ed_user.text().strip()
        p = self.ed_pass.text().strip()
        if not u or not p:
            self.show_error("Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu.")
            return

        if not self._ensure_connection():
            return

        self.pending_cmd = "LOGIN"
        self.net.send(build_cmd("LOGIN", u, p))

    def do_register(self):
        self.lbl_error.hide()
        u = self.ed_user.text().strip()
        p = self.ed_pass.text().strip()
        if not u or not p:
            self.show_error("Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu.")
            return

        if len(u) < 3 or len(u) > 20:
            self.show_error("Tên đăng nhập phải từ 3 đến 20 ký tự.")
            return
        if len(p) < 6:
            self.show_error("Mật khẩu phải có tối thiểu 6 ký tự.")
            return

        if not self._ensure_connection():
            return

        self.pending_cmd = "REGISTER"
        self.net.send(build_cmd("REGISTER", u, p))

    def on_response(self, payload: str):
        if not self.pending_cmd:
            return

        cmd = self.pending_cmd
        self.pending_cmd = None

        if payload.startswith("ERR|"):
            _, friendly_msg = parse_err(payload)
            self.show_error(friendly_msg)
            return

        parts = payload.split("|")
        if cmd == "REGISTER":
            if parts[0] == "OK":
                QMessageBox.information(self, "Thành công", "Đăng ký tài khoản thành công! Vui lòng nhấn Đăng nhập.")
                self.lbl_error.hide()
        elif cmd == "LOGIN":
            if parts[0] == "OK" and len(parts) >= 3:
                token = parts[1]
                role = parts[2]
                self.app_state.token = token
                self.app_state.username = self.ed_user.text().strip()
                self.app_state.role = role

                # Check if resume available: OK|token|role|RESUME|rid
                if len(parts) >= 5 and parts[3] == "RESUME":
                    rid = int(parts[4])
                    reply = QMessageBox.question(
                        self,
                        "Khôi phục bài thi",
                        f"Bạn có bài thi đang diễn ra tại phòng #{rid}. Bạn có muốn vào lại để tiếp tục thi?",
                        QMessageBox.Yes | QMessageBox.No,
                    )
                    if reply == QMessageBox.Yes:
                        self.app_state.room_id = rid
                        self.pending_cmd = "RESUME"
                        self.net.send(build_cmd("RESUME", token, rid))
                        return

                self.goto("dashboard")
        elif cmd == "RESUME":
            if parts[0] == "OK" and len(parts) >= 6:
                # OK|RESUME|rid|n|giây_còn|ans_mask|qrec...
                from proto import parse_qrec
                rid = int(parts[2])
                num_q = int(parts[3])
                sec_left = int(parts[4])
                mask = parts[5]
                qrecs = [parse_qrec(q) for q in parts[6:]]

                self.app_state.exam = {
                    "rid": rid,
                    "n": num_q,
                    "sec": sec_left,
                    "mask": mask,
                    "questions": qrecs,
                    "answers": [-1] * (num_q + 1),
                    "mode": "room",
                }
                self.goto("exam")
