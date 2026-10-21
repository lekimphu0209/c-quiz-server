import time
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QFrame,
    QDialog,
)
from proto import build_cmd, parse_err, unescape_field


class DetailAnswersDialog(QDialog):
    """Dialog showing answer key and explanations for each question."""

    def __init__(self, details: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chi tiết đáp án & Giải thích")
        self.resize(650, 480)
        self._init_ui(details)

    def _init_ui(self, details: list):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        lbl_title = QLabel("KẾT QUẢ TỪNG CÂU HỎI")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #f8fafc;")
        layout.addWidget(lbl_title)

        tbl = QTableWidget()
        tbl.setColumnCount(4)
        tbl.setHorizontalHeaderLabels(["Câu", "Bạn chọn", "Đáp án đúng", "Giải thích"])
        tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setRowCount(len(details))

        opts_map = {0: "A", 1: "B", 2: "C", 3: "D", -1: "Chưa chọn"}
        for r, item in enumerate(details):
            qidx, chosen, correct, expl = item
            is_correct = (chosen == correct)

            it_q = QTableWidgetItem(str(qidx))
            it_ch = QTableWidgetItem(opts_map.get(chosen, str(chosen)))
            it_co = QTableWidgetItem(opts_map.get(correct, str(correct)))
            it_ex = QTableWidgetItem(expl)

            color = "#10b981" if is_correct else "#ef4444"
            for it in (it_q, it_ch, it_co, it_ex):
                it.setForeground(Qt.white)
                if not is_correct and it in (it_ch,):
                    it.setForeground(Qt.red)
                elif is_correct:
                    it.setForeground(Qt.green)

            tbl.setItem(r, 0, it_q)
            tbl.setItem(r, 1, it_ch)
            tbl.setItem(r, 2, it_co)
            tbl.setItem(r, 3, it_ex)

        layout.addWidget(tbl)

        btn_close = QPushButton("Đóng")
        btn_close.setProperty("secondary", "true")
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)


class ResultScreen(QWidget):
    """Result and Leaderboard screen (S6)."""

    def __init__(self, app_state, net, goto_callback, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.net = net
        self.goto = goto_callback
        self.pending_cmd = None

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 28, 40, 36)
        layout.setSpacing(20)

        # Header Title
        self.lbl_title = QLabel("KẾT QUẢ BÀI THI")
        self.lbl_title.setProperty("heading", "true")
        layout.addWidget(self.lbl_title)

        # Showcase Score Card
        score_card = QFrame()
        score_card.setProperty("card", "true")
        sc_layout = QVBoxLayout(score_card)
        sc_layout.setContentsMargins(32, 24, 32, 24)
        sc_layout.setSpacing(10)
        sc_layout.setAlignment(Qt.AlignCenter)

        self.lbl_trophy = QLabel("🏆")
        self.lbl_trophy.setStyleSheet("font-size: 44px;")
        self.lbl_trophy.setAlignment(Qt.AlignCenter)
        sc_layout.addWidget(self.lbl_trophy)

        self.lbl_score_main = QLabel("8 / 10 CÂU ĐÚNG")
        self.lbl_score_main.setStyleSheet("font-size: 28px; font-weight: 900; color: #10b981;")
        self.lbl_score_main.setAlignment(Qt.AlignCenter)
        sc_layout.addWidget(self.lbl_score_main)

        self.lbl_subtext = QLabel("Tỷ lệ chính xác: 80.0% • Thứ hạng: 1")
        self.lbl_subtext.setStyleSheet("font-size: 14px; font-weight: 600; color: #94a3b8;")
        self.lbl_subtext.setAlignment(Qt.AlignCenter)
        sc_layout.addWidget(self.lbl_subtext)

        layout.addWidget(score_card)

        # Leaderboard Section
        self.leaderboard_box = QFrame()
        self.leaderboard_box.setProperty("card", "true")
        lb_layout = QVBoxLayout(self.leaderboard_box)
        lb_layout.setContentsMargins(24, 20, 24, 20)
        lb_layout.setSpacing(12)

        self.lbl_lb_title = QLabel("BẢNG XẾP HẠNG PHÒNG THI")
        self.lbl_lb_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #f1f5f9;")
        lb_layout.addWidget(self.lbl_lb_title)

        self.tbl_rank = QTableWidget()
        self.tbl_rank.setColumnCount(4)
        self.tbl_rank.setHorizontalHeaderLabels(["Hạng", "Thí sinh", "Điểm số", "Thời gian nộp"])
        self.tbl_rank.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_rank.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_rank.setSelectionBehavior(QTableWidget.SelectRows)
        lb_layout.addWidget(self.tbl_rank)

        layout.addWidget(self.leaderboard_box, stretch=1)

        # Bottom Actions
        actions = QHBoxLayout()
        self.btn_detail = QPushButton("🔍 Xem đáp án & giải thích")
        self.btn_detail.setProperty("secondary", "true")
        self.btn_detail.setFixedHeight(42)
        self.btn_detail.clicked.connect(self.do_view_detail)

        self.btn_lobby = QPushButton("← Về sảnh phòng")
        self.btn_lobby.setProperty("secondary", "true")
        self.btn_lobby.setFixedHeight(42)
        self.btn_lobby.clicked.connect(lambda: self.goto("lobby"))

        self.btn_home = QPushButton("🏠 Về trang chủ")
        self.btn_home.setFixedHeight(42)
        self.btn_home.setStyleSheet("background-color: #4f46e5; color: white; font-weight: 700; border-radius: 8px;")
        self.btn_home.clicked.connect(lambda: self.goto("dashboard"))

        actions.addWidget(self.btn_detail)
        actions.addStretch()
        actions.addWidget(self.btn_lobby)
        actions.addWidget(self.btn_home)
        layout.addLayout(actions)

    def on_enter(self):
        self.pending_cmd = None
        res = getattr(self.app_state, "last_result", {})
        if not res:
            return

        rid = res.get("rid", getattr(self.app_state, "room_id", 0))
        mode = res.get("mode", "room")
        score = res.get("score", 0)
        total = res.get("total", 10)
        rank = res.get("rank", "-")

        pct = (score / total * 100.0) if total > 0 else 0.0
        self.lbl_score_main.setText(f"{score} / {total} CÂU ĐÚNG")
        rank_str = f" • Thứ hạng: {rank}" if rank != "-" and mode != "practice" else ""
        self.lbl_subtext.setText(f"Tỷ lệ chính xác: {pct:.1f}%{rank_str}")

        if pct >= 80:
            self.lbl_trophy.setText("🏆")
            self.lbl_score_main.setStyleSheet("font-size: 28px; font-weight: 900; color: #10b981;")
        elif pct >= 50:
            self.lbl_trophy.setText("🎯")
            self.lbl_score_main.setStyleSheet("font-size: 28px; font-weight: 900; color: #38bdf8;")
        else:
            self.lbl_trophy.setText("📝")
            self.lbl_score_main.setStyleSheet("font-size: 28px; font-weight: 900; color: #f59e0b;")

        is_practice = (mode == "practice")
        self.leaderboard_box.setVisible(not is_practice)
        self.btn_lobby.setVisible(not is_practice)
        self.btn_detail.setVisible(True)

        if not is_practice and rid:
            # Query full room results to populate leaderboard table
            self.pending_cmd = "ROOM_RESULT"
            self.net.send(build_cmd("ROOM_RESULT", self.app_state.token, rid))

    def on_leave(self):
        self.pending_cmd = None

    def do_view_detail(self):
        # Request latest attempt history to obtain att_id
        self.pending_cmd = "HISTORY_FOR_DETAIL"
        mode = "practice" if self.app_state.last_result.get("mode") == "practice" else "all"
        self.net.send(build_cmd("HISTORY", self.app_state.token, mode))

    def on_response(self, payload: str):
        if not self.pending_cmd:
            return

        cmd = self.pending_cmd
        self.pending_cmd = None

        if payload.startswith("ERR|"):
            _, friendly_msg = parse_err(payload)
            QMessageBox.warning(self, "Thông báo lỗi", friendly_msg)
            return

        parts = payload.split("|")
        if cmd == "ROOM_RESULT":
            if parts[0] == "OK":
                # OK|num_q|rank:user:score:ts...
                self.tbl_rank.setRowCount(0)
                items = parts[2:] if len(parts) > 2 else []
                self.tbl_rank.setRowCount(len(items))

                for r, item in enumerate(items):
                    f = item.split(":")
                    if len(f) < 4:
                        continue
                    rk, user, sc, ts = f[:4]
                    ts_str = time.strftime("%H:%M:%S", time.localtime(int(ts))) if ts.isdigit() and int(ts) > 0 else "-"

                    it_rk = QTableWidgetItem(rk)
                    it_u = QTableWidgetItem(user)
                    it_sc = QTableWidgetItem(f"{sc}/{parts[1]}")
                    it_ts = QTableWidgetItem(ts_str)

                    # Highlight user
                    if user == self.app_state.username:
                        for it in (it_rk, it_u, it_sc, it_ts):
                            it.setBackground(Qt.darkBlue)
                            it.setForeground(Qt.yellow)
                        self.lbl_subtext.setText(f"Tỷ lệ chính xác: {int(sc)/int(parts[1])*100:.1f}% • Thứ hạng: {rk}")

                    self.tbl_rank.setItem(r, 0, it_rk)
                    self.tbl_rank.setItem(r, 1, it_u)
                    self.tbl_rank.setItem(r, 2, it_sc)
                    self.tbl_rank.setItem(r, 3, it_ts)

        elif cmd == "HISTORY_FOR_DETAIL":
            if parts[0] == "OK" and len(parts) > 1 and parts[1]:
                # First record is latest attempt: att_id:ts:mode:name:score:num_q
                first = parts[1].split(":")
                att_id = int(first[0])
                self.pending_cmd = "HISTORY_DETAIL"
                self.net.send(build_cmd("HISTORY_DETAIL", self.app_state.token, att_id))
            else:
                QMessageBox.information(self, "Thông báo", "Chưa có dữ liệu bài làm để xem chi tiết.")

        elif cmd == "HISTORY_DETAIL":
            if parts[0] == "OK":
                # OK|qidx:chosen:correct:expl|...
                details = []
                for p in parts[1:]:
                    if not p:
                        continue
                    fields = p.split(":")
                    if len(fields) >= 4:
                        qidx = int(fields[0])
                        chosen = int(fields[1])
                        correct = int(fields[2])
                        expl = unescape_field(fields[3])
                        details.append((qidx, chosen, correct, expl))

                dlg = DetailAnswersDialog(details, self)
                dlg.exec_()
