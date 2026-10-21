from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFrame,
    QDialog,
    QSpinBox,
    QComboBox,
    QMessageBox,
)
from proto import build_cmd, parse_err, parse_qrec


class PracticeDialog(QDialog):
    """Configuration dialog for practice mode."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cấu hình Luyện tập")
        self.setFixedSize(360, 280)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        card = QFrame()
        card.setProperty("card", "true")
        form = QVBoxLayout(card)

        # Number of questions
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Số câu hỏi (1-100):"))
        self.spn_count = QSpinBox()
        self.spn_count.setRange(1, 100)
        self.spn_count.setValue(5)
        row1.addWidget(self.spn_count)
        form.addLayout(row1)

        # Duration
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Thời gian (giây):"))
        self.spn_sec = QSpinBox()
        self.spn_sec.setRange(10, 7200)
        self.spn_sec.setValue(300)
        self.spn_sec.setSingleStep(30)
        row2.addWidget(self.spn_sec)
        form.addLayout(row2)

        # Difficulty
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Độ khó:"))
        self.cmb_diff = QComboBox()
        self.cmb_diff.addItems(["mixed", "easy", "medium", "hard"])
        row3.addWidget(self.cmb_diff)
        form.addLayout(row3)

        # Topic
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Chủ đề:"))
        self.cmb_topic = QComboBox()
        self.cmb_topic.addItems(["all", "net", "c", "os"])
        row4.addWidget(self.cmb_topic)
        form.addLayout(row4)

        layout.addWidget(card)

        # Action buttons
        btn_box = QHBoxLayout()
        self.btn_ok = QPushButton("BẮT ĐẦU")
        self.btn_ok.setProperty("success", "true")
        self.btn_ok.clicked.connect(self.accept)

        self.btn_cancel = QPushButton("HỦY")
        self.btn_cancel.setProperty("secondary", "true")
        self.btn_cancel.clicked.connect(self.reject)

        btn_box.addWidget(self.btn_ok)
        btn_box.addWidget(self.btn_cancel)
        layout.addLayout(btn_box)

    def get_config(self):
        return (
            self.spn_count.value(),
            self.spn_sec.value(),
            self.cmb_diff.currentText(),
            self.cmb_topic.currentText(),
        )


class DashboardScreen(QWidget):
    def __init__(self, app_state, net, goto_callback, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.net = net
        self.goto = goto_callback
        self.pending_cmd = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 40)
        layout.setSpacing(24)

        # Header Bar
        header = QFrame()
        header.setProperty("card", "true")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 14, 20, 14)

        user_info = QVBoxLayout()
        self.lbl_welcome = QLabel("Xin chào!")
        self.lbl_welcome.setProperty("heading", "true")
        self.lbl_role = QLabel("Vai trò: Thí sinh")
        self.lbl_role.setProperty("subheading", "true")
        user_info.addWidget(self.lbl_welcome)
        user_info.addWidget(self.lbl_role)

        self.btn_logout = QPushButton("Đăng xuất")
        self.btn_logout.setProperty("danger", "true")
        self.btn_logout.setFixedWidth(120)
        self.btn_logout.clicked.connect(self.do_logout)

        header_layout.addLayout(user_info)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_logout)

        layout.addWidget(header)

        # Mode Selection Grid
        grid_container = QWidget()
        grid = QGridLayout(grid_container)
        grid.setSpacing(20)
        grid.setContentsMargins(0, 10, 0, 10)

        # Card 1: Exam Mode
        self.btn_exam = self._create_nav_card(
            "CHẾ ĐỘ THI PHÒNG",
            "Tạo hoặc tham gia phòng thi trắc nghiệm trực tuyến cùng các thí sinh khác với thời gian thực.",
            "#6366f1",
            self.go_lobby,
        )
        grid.addWidget(self.btn_exam, 0, 0)

        # Card 2: Practice Mode
        self.btn_practice = self._create_nav_card(
            "TỰ LUYỆN TẬP",
            "Luyện tập cá nhân theo mức độ khó (Dễ/TB/Khó) và chủ đề tùy chọn, không giới hạn.",
            "#10b981",
            self.do_practice,
        )
        grid.addWidget(self.btn_practice, 0, 1)

        # Card 3: History & Stats
        self.btn_history = self._create_nav_card(
            "LỊCH SỬ & THỐNG KÊ",
            "Xem lại lịch sử các bài đã làm, chi tiết đúng/sai từng câu và biểu đồ tiến độ năng lực.",
            "#0ea5e9",
            lambda: self.goto("history"),
        )
        grid.addWidget(self.btn_history, 1, 0)

        # Card 4: Admin Management
        self.btn_admin = self._create_nav_card(
            "QUẢN TRỊ HỆ THỐNG",
            "Ngân hàng câu hỏi, thêm/xóa/import CSV và xem thống kê tổng hợp toàn hệ thống.",
            "#f59e0b",
            lambda: self.goto("admin"),
        )
        grid.addWidget(self.btn_admin, 1, 1)

        layout.addWidget(grid_container)
        layout.addStretch()

    def _create_nav_card(self, title: str, desc: str, accent_color: str, on_click) -> QFrame:
        card = QFrame()
        card.setProperty("card", "true")
        card.setCursor(Qt.PointingHandCursor)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(12)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {accent_color};")

        lbl_desc = QLabel(desc)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #94a3b8; font-size: 13px; line-height: 1.4;")

        btn = QPushButton("Truy cập →")
        btn.setStyleSheet(f"background-color: {accent_color}; border-radius: 6px; font-weight: 700;")
        btn.clicked.connect(on_click)

        card_layout.addWidget(lbl_title)
        card_layout.addWidget(lbl_desc)
        card_layout.addStretch()
        card_layout.addWidget(btn, alignment=Qt.AlignRight)

        return card

    def on_enter(self):
        self.lbl_welcome.setText(f"Xin chào, {self.app_state.username}!")
        role_text = "Quản trị viên (Admin)" if self.app_state.role == "admin" else "Thí sinh"
        self.lbl_role.setText(f"Vai trò: {role_text}")
        self.btn_admin.setVisible(self.app_state.role == "admin")
        self.pending_cmd = None

    def on_leave(self):
        self.pending_cmd = None

    def go_lobby(self):
        self.goto("lobby")

    def do_practice(self):
        dlg = PracticeDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            num_q, sec, diff, topic = dlg.get_config()
            self.pending_cmd = "PRACTICE"
            self.net.send(build_cmd("PRACTICE", self.app_state.token, num_q, sec, diff, topic))

    def do_logout(self):
        reply = QMessageBox.question(
            self,
            "Đăng xuất",
            "Bạn có chắc chắn muốn đăng xuất?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.pending_cmd = "LOGOUT"
            self.net.send(build_cmd("LOGOUT", self.app_state.token))

    def on_response(self, payload: str):
        if not self.pending_cmd:
            return

        cmd = self.pending_cmd
        self.pending_cmd = None

        if payload.startswith("ERR|"):
            _, friendly_msg = parse_err(payload)
            QMessageBox.warning(self, "Lỗi", friendly_msg)
            return

        parts = payload.split("|")
        if cmd == "LOGOUT":
            self.app_state.token = ""
            self.app_state.username = ""
            self.app_state.role = "user"
            self.goto("login")
        elif cmd == "PRACTICE":
            if parts[0] == "OK" and len(parts) >= 6:
                # OK|PRACTICE|rid|n|sec|qrec...
                rid = int(parts[2])
                num_q = int(parts[3])
                sec = int(parts[4])
                qrecs = [parse_qrec(q) for q in parts[5:]]

                self.app_state.exam = {
                    "rid": rid,
                    "n": num_q,
                    "sec": sec,
                    "questions": qrecs,
                    "answers": [-1] * (num_q + 1),
                    "mode": "practice",
                }
                self.goto("exam")
