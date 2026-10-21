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
    QComboBox,
    QTabWidget,
    QMessageBox,
    QFrame,
    QProgressBar,
    QScrollArea,
)
from proto import build_cmd, parse_err, unescape_field
from screens.result import DetailAnswersDialog

try:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


class HistoryScreen(QWidget):
    """History records and statistical performance analytics screen (S7)."""

    def __init__(self, app_state, net, goto_callback, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.net = net
        self.goto = goto_callback
        self.pending_cmd = None

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 32)
        layout.setSpacing(18)

        # Header Bar
        header = QHBoxLayout()
        self.btn_back = QPushButton("← Trang chủ")
        self.btn_back.setProperty("secondary", "true")
        self.btn_back.setFixedWidth(120)
        self.btn_back.clicked.connect(lambda: self.goto("dashboard"))

        lbl_title = QLabel("LỊCH SỬ & THỐNG KÊ KẾT QUẢ")
        lbl_title.setProperty("heading", "true")

        self.btn_refresh = QPushButton("🔄 Làm mới")
        self.btn_refresh.setProperty("secondary", "true")
        self.btn_refresh.setFixedWidth(110)
        self.btn_refresh.clicked.connect(self.reload_data)

        header.addWidget(self.btn_back)
        header.addSpacing(12)
        header.addWidget(lbl_title)
        header.addStretch()
        header.addWidget(self.btn_refresh)
        layout.addLayout(header)

        # Tabs container
        self.tabs = QTabWidget()
        self.tab_history = QWidget()
        self.tab_stats = QWidget()

        self._init_history_tab()
        self._init_stats_tab()

        self.tabs.addTab(self.tab_history, "📜 Lịch sử làm bài")
        self.tabs.addTab(self.tab_stats, "📊 Biểu đồ thống kê")
        layout.addWidget(self.tabs)

    def _init_history_tab(self):
        layout = QVBoxLayout(self.tab_history)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Mode Filter
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Chế độ:"))
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["Tất cả", "Thi phòng", "Luyện tập"])
        self.cmb_mode.currentIndexChanged.connect(self.on_filter_changed)
        self.cmb_mode.setFixedWidth(140)
        filter_row.addWidget(self.cmb_mode)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # History Table
        self.tbl_history = QTableWidget()
        self.tbl_history.setColumnCount(6)
        self.tbl_history.setHorizontalHeaderLabels([
            "ID", "Thời gian", "Chế độ", "Tên bài thi", "Điểm số", "Chi tiết"
        ])
        self.tbl_history.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tbl_history.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_history.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.tbl_history)

    def _init_stats_tab(self):
        layout = QVBoxLayout(self.tab_stats)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Summary Metrics Row
        metrics_row = QHBoxLayout()
        self.card_attempts = self._create_metric_card("TỔNG SỐ BÀI THI", "0 bài", "#6366f1")
        self.card_avg = self._create_metric_card("ĐIỂM TRUNG BÌNH", "0.0%", "#10b981")
        metrics_row.addWidget(self.card_attempts)
        metrics_row.addWidget(self.card_avg)
        layout.addLayout(metrics_row)

        # Charts / Progress section
        if HAS_MATPLOTLIB:
            self.fig = Figure(figsize=(7, 4), facecolor="#1e293b")
            self.canvas = FigureCanvas(self.fig)
            layout.addWidget(self.canvas, stretch=1)
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("background: transparent; border: none;")
            content = QWidget()
            self.vbox_bars = QVBoxLayout(content)
            self.vbox_bars.setSpacing(12)
            scroll.setWidget(content)
            layout.addWidget(scroll, stretch=1)

    def _create_metric_card(self, title: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setProperty("card", "true")
        l = QVBoxLayout(card)
        l.setContentsMargins(16, 12, 16, 12)
        l.setSpacing(4)
        t = QLabel(title)
        t.setStyleSheet("font-size: 11px; font-weight: 700; color: #94a3b8;")
        v = QLabel(value)
        v.setStyleSheet(f"font-size: 22px; font-weight: 900; color: {color};")
        l.addWidget(t)
        l.addWidget(v)
        card.val_label = v
        return card

    def on_enter(self):
        self.reload_data()

    def on_leave(self):
        self.pending_cmd = None

    def reload_data(self):
        self.fetch_history()
        self.fetch_stats()

    def on_filter_changed(self):
        self.fetch_history()

    def fetch_history(self):
        mode_idx = self.cmb_mode.currentIndex()
        mode_val = "all" if mode_idx == 0 else ("room" if mode_idx == 1 else "practice")
        self.pending_cmd = "HISTORY"
        self.net.send(build_cmd("HISTORY", self.app_state.token, mode_val))

    def fetch_stats(self):
        self.pending_cmd = "STATS"
        self.net.send(build_cmd("STATS", self.app_state.token))

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
        if cmd == "HISTORY":
            if parts[0] == "OK":
                self.tbl_history.setRowCount(0)
                items = parts[1:] if len(parts) > 1 and parts[1] else []
                self.tbl_history.setRowCount(len(items))

                for r, item in enumerate(items):
                    fields = item.split(":")
                    if len(fields) < 6:
                        continue
                    att_id, ts, mode, name, score, num_q = fields[:6]
                    ts_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(int(ts))) if ts.isdigit() and int(ts) > 0 else "-"
                    mode_name = "Luyện tập" if mode == "practice" else "Thi phòng"

                    self.tbl_history.setItem(r, 0, QTableWidgetItem(att_id))
                    self.tbl_history.setItem(r, 1, QTableWidgetItem(ts_str))
                    self.tbl_history.setItem(r, 2, QTableWidgetItem(mode_name))
                    self.tbl_history.setItem(r, 3, QTableWidgetItem(unescape_field(name)))
                    self.tbl_history.setItem(r, 4, QTableWidgetItem(f"{score}/{num_q}"))

                    btn = QPushButton("Xem giải thích")
                    btn.setProperty("secondary", "true")
                    btn.setFixedSize(110, 28)
                    btn.clicked.connect(lambda ch, aid=att_id: self.view_detail(aid))
                    self.tbl_history.setCellWidget(r, 5, btn)

        elif cmd == "STATS":
            if parts[0] == "OK" and len(parts) >= 9:
                attempts = parts[1]
                avg_x100 = int(parts[2]) if parts[2].isdigit() else 0
                avg_pct = avg_x100 / 100.0

                self.card_attempts.val_label.setText(f"{attempts} bài")
                self.card_avg.val_label.setText(f"{avg_pct:.1f}%")

                easy_c, easy_tot = int(parts[3]), int(parts[4])
                med_c, med_tot = int(parts[5]), int(parts[6])
                hard_c, hard_tot = int(parts[7]), int(parts[8])

                topics_str = parts[9] if len(parts) > 9 else ""

                if HAS_MATPLOTLIB:
                    self._render_matplotlib(easy_c, easy_tot, med_c, med_tot, hard_c, hard_tot)
                else:
                    self._render_fallback_bars(easy_c, easy_tot, med_c, med_tot, hard_c, hard_tot, topics_str)

        elif cmd == "HISTORY_DETAIL":
            if parts[0] == "OK":
                details = []
                for p in parts[1:]:
                    if not p:
                        continue
                    f = p.split(":")
                    if len(f) >= 4:
                        details.append((int(f[0]), int(f[1]), int(f[2]), unescape_field(f[3])))
                dlg = DetailAnswersDialog(details, self)
                dlg.exec_()

    def view_detail(self, att_id: str):
        self.pending_cmd = "HISTORY_DETAIL"
        self.net.send(build_cmd("HISTORY_DETAIL", self.app_state.token, att_id))

    def _render_matplotlib(self, easy_c, easy_tot, med_c, med_tot, hard_c, hard_tot):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.set_facecolor("#1e293b")

        categories = ["Dễ", "Trung bình", "Khó"]
        rates = [
            (easy_c / easy_tot * 100) if easy_tot > 0 else 0,
            (med_c / med_tot * 100) if med_tot > 0 else 0,
            (hard_c / hard_tot * 100) if hard_tot > 0 else 0,
        ]
        colors = ["#10b981", "#38bdf8", "#f43f5e"]

        bars = ax.bar(categories, rates, color=colors, width=0.45)
        ax.set_ylim(0, 100)
        ax.set_ylabel("Tỷ lệ đúng (%)", color="#94a3b8", fontsize=11)
        ax.set_title("Tỷ lệ trả lời đúng theo mức độ khó", color="#f8fafc", fontsize=13, fontweight="bold", pad=12)
        ax.tick_params(colors="#cbd5e1")
        for spine in ax.spines.values():
            spine.set_color("#475569")

        for bar in bars:
            yval = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2.0, yval + 2, f"{yval:.1f}%", ha='center', va='bottom', color='#ffffff', fontweight='bold', fontsize=10)

        self.fig.tight_layout()
        self.canvas.draw()

    def _render_fallback_bars(self, easy_c, easy_tot, med_c, med_tot, hard_c, hard_tot, topics_str):
        # Clear layout
        while self.vbox_bars.count():
            item = self.vbox_bars.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        lbl_hdr = QLabel("TỶ LỆ ĐÚNG THEO ĐỘ KHÓ")
        lbl_hdr.setStyleSheet("font-size: 13px; font-weight: 700; color: #f1f5f9; margin-top: 8px;")
        self.vbox_bars.addWidget(lbl_hdr)

        diffs = [
            ("Mức Dễ", easy_c, easy_tot, "#10b981"),
            ("Trung Bình", med_c, med_tot, "#38bdf8"),
            ("Mức Khó", hard_c, hard_tot, "#f43f5e"),
        ]
        for name, c, tot, color in diffs:
            pct = int((c / tot * 100)) if tot > 0 else 0
            row = QHBoxLayout()
            lbl = QLabel(f"{name} ({c}/{tot}):")
            lbl.setFixedWidth(130)
            lbl.setStyleSheet("color: #cbd5e1; font-weight: 600;")

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(pct)
            bar.setStyleSheet(f"""
                QProgressBar {{
                    border: 1px solid #334155;
                    border-radius: 6px;
                    text-align: center;
                    background-color: #0f172a;
                    color: white;
                    font-weight: bold;
                    height: 22px;
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                    border-radius: 5px;
                }}
            """)
            row.addWidget(lbl)
            row.addWidget(bar)
            self.vbox_bars.addLayout(row)

        self.vbox_bars.addStretch()
