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
    QMessageBox,
    QFrame,
    QDialog,
    QLineEdit,
    QTextEdit,
    QRadioButton,
    QButtonGroup,
    QProgressBar,
    QInputDialog,
)
from proto import build_cmd, parse_err, unescape_field

try:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


class AddQuestionDialog(QDialog):
    """Dialog form for adding a new question to the bank."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Thêm câu hỏi mới")
        self.resize(520, 560)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        card = QFrame()
        card.setProperty("card", "true")
        form = QVBoxLayout(card)
        form.setSpacing(10)

        form.addWidget(QLabel("Nội dung câu hỏi:"))
        self.txt_content = QTextEdit()
        self.txt_content.setMaximumHeight(70)
        self.txt_content.setPlaceholderText("Nhập nội dung câu hỏi trắc nghiệm...")
        form.addWidget(self.txt_content)

        form.addWidget(QLabel("Các lựa chọn đáp án (A, B, C, D) & chọn đáp án đúng:"))
        self.ed_opts = []
        self.rdo_group = QButtonGroup(self)
        labels = ["A", "B", "C", "D"]

        for i, lbl in enumerate(labels):
            row = QHBoxLayout()
            rdo = QRadioButton(f"{lbl}:")
            rdo.setFixedWidth(40)
            if i == 0:
                rdo.setChecked(True)
            self.rdo_group.addButton(rdo, i)

            ed = QLineEdit()
            ed.setPlaceholderText(f"Nội dung đáp án {lbl}")
            self.ed_opts.append(ed)

            row.addWidget(rdo)
            row.addWidget(ed)
            form.addLayout(row)

        row_meta = QHBoxLayout()
        v_diff = QVBoxLayout()
        v_diff.addWidget(QLabel("Độ khó:"))
        self.cmb_diff = QComboBox()
        self.cmb_diff.addItems(["easy", "medium", "hard"])
        self.cmb_diff.setCurrentText("medium")
        v_diff.addWidget(self.cmb_diff)

        v_topic = QVBoxLayout()
        v_topic.addWidget(QLabel("Chủ đề:"))
        self.ed_topic = QLineEdit()
        self.ed_topic.setPlaceholderText("VD: mang, he_dieu_hanh")
        self.ed_topic.setText("mang")
        v_topic.addWidget(self.ed_topic)

        row_meta.addLayout(v_diff)
        row_meta.addLayout(v_topic)
        form.addLayout(row_meta)

        form.addWidget(QLabel("Giải thích đáp án (tùy chọn):"))
        self.ed_expl = QLineEdit()
        self.ed_expl.setPlaceholderText("Giải thích ngắn gọn cho đáp án đúng...")
        form.addWidget(self.ed_expl)

        layout.addWidget(card)

        # Buttons
        btns = QHBoxLayout()
        self.btn_cancel = QPushButton("Hủy")
        self.btn_cancel.setProperty("secondary", "true")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_save = QPushButton("Lưu câu hỏi")
        self.btn_save.setProperty("success", "true")
        self.btn_save.setStyleSheet(
            "background-color: #10b981; color: white; font-weight: 700; border-radius: 6px; padding: 8px 16px;"
        )
        self.btn_save.clicked.connect(self.validate_and_accept)

        btns.addStretch()
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_save)
        layout.addLayout(btns)

    def validate_and_accept(self):
        content = self.txt_content.toPlainText().strip()
        opts = [ed.text().strip() for ed in self.ed_opts]
        topic = self.ed_topic.text().strip()

        if not content:
            QMessageBox.warning(self, "Lỗi nhập liệu", "Vui lòng nhập nội dung câu hỏi!")
            return
        for i, o in enumerate(opts):
            if not o:
                QMessageBox.warning(self, "Lỗi nhập liệu", f"Vui lòng nhập nội dung đáp án {chr(ord('A')+i)}!")
                return
        if not topic:
            QMessageBox.warning(self, "Lỗi nhập liệu", "Vui lòng nhập chủ đề câu hỏi!")
            return

        self.accept()

    def get_data(self):
        content = self.txt_content.toPlainText().strip()
        opts = [ed.text().strip() for ed in self.ed_opts]
        correct = self.rdo_group.checkedId()
        diff = self.cmb_diff.currentText()
        topic = self.ed_topic.text().strip()
        expl = self.ed_expl.text().strip()
        return content, opts[0], opts[1], opts[2], opts[3], correct, diff, topic, expl


class AdminScreen(QWidget):
    """Admin management screen for question bank and system stats (S8)."""

    def __init__(self, app_state, net, goto_callback, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.net = net
        self.goto = goto_callback
        self.pending_cmd = None

        self.all_questions = []
        self.selected_qid = None

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

        lbl_title = QLabel("QUẢN TRỊ HỆ THỐNG — NGÂN HÀNG CÂU HỎI")
        lbl_title.setProperty("heading", "true")

        self.btn_refresh = QPushButton("🔄 Làm mới")
        self.btn_refresh.setProperty("secondary", "true")
        self.btn_refresh.setFixedWidth(110)
        self.btn_refresh.clicked.connect(self.reload_all)

        header.addWidget(self.btn_back)
        header.addSpacing(12)
        header.addWidget(lbl_title)
        header.addStretch()
        header.addWidget(self.btn_refresh)
        layout.addLayout(header)

        # Actions Row
        actions_row = QHBoxLayout()
        self.btn_add = QPushButton("＋ Thêm câu hỏi")
        self.btn_add.setProperty("success", "true")
        self.btn_add.clicked.connect(self.do_add_question)

        self.btn_delete = QPushButton("🗑 Xóa đã chọn")
        self.btn_delete.setProperty("danger", "true")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self.do_delete_question)

        self.btn_import = QPushButton("📂 Import CSV")
        self.btn_import.setProperty("secondary", "true")
        self.btn_import.clicked.connect(self.do_import_csv)

        actions_row.addWidget(self.btn_add)
        actions_row.addWidget(self.btn_delete)
        actions_row.addWidget(self.btn_import)
        actions_row.addStretch()

        actions_row.addWidget(QLabel("Lọc độ khó:"))
        self.cmb_filter_diff = QComboBox()
        self.cmb_filter_diff.addItems(["Tất cả", "easy", "medium", "hard"])
        self.cmb_filter_diff.currentIndexChanged.connect(self._apply_filter)
        self.cmb_filter_diff.setFixedWidth(120)
        actions_row.addWidget(self.cmb_filter_diff)

        layout.addLayout(actions_row)

        # Questions Table
        self.tbl_questions = QTableWidget()
        self.tbl_questions.setColumnCount(5)
        self.tbl_questions.setHorizontalHeaderLabels(["ID", "Nội dung", "Đ.án đúng", "Độ khó", "Chủ đề"])
        self.tbl_questions.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_questions.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl_questions.setSelectionMode(QTableWidget.SingleSelection)
        self.tbl_questions.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_questions.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.tbl_questions, stretch=2)

        # System Statistics Panel
        stats_box = QFrame()
        stats_box.setProperty("card", "true")
        s_layout = QVBoxLayout(stats_box)
        s_layout.setContentsMargins(20, 16, 20, 16)
        s_layout.setSpacing(10)

        lbl_stats_hdr = QLabel("THỐNG KÊ TOÀN HỆ THỐNG (STATS ALL)")
        lbl_stats_hdr.setStyleSheet("font-size: 14px; font-weight: 800; color: #f59e0b;")
        s_layout.addWidget(lbl_stats_hdr)

        m_row = QHBoxLayout()
        self.lbl_sys_attempts = QLabel("Tổng lượt thi: 0")
        self.lbl_sys_attempts.setStyleSheet("font-size: 14px; font-weight: 700; color: #e2e8f0;")
        self.lbl_sys_avg = QLabel("Điểm trung bình: 0.0%")
        self.lbl_sys_avg.setStyleSheet("font-size: 14px; font-weight: 700; color: #10b981;")
        m_row.addWidget(self.lbl_sys_attempts)
        m_row.addSpacing(24)
        m_row.addWidget(self.lbl_sys_avg)
        m_row.addStretch()
        s_layout.addLayout(m_row)

        self.layout_stats_bars = QVBoxLayout()
        s_layout.addLayout(self.layout_stats_bars)

        layout.addWidget(stats_box, stretch=1)

    def on_enter(self):
        if self.app_state.role != "admin":
            QMessageBox.warning(self, "Từ chối truy cập", "Trang này chỉ dành cho Quản trị viên (Admin)!")
            self.goto("dashboard")
            return
        self.reload_all()

    def on_leave(self):
        self.pending_cmd = None

    def reload_all(self):
        self.fetch_questions()
        self.fetch_sys_stats()

    def fetch_questions(self):
        self.pending_cmd = "LIST_QUESTIONS"
        self.net.send(build_cmd("LIST_QUESTIONS", self.app_state.token))

    def fetch_sys_stats(self):
        self.pending_cmd = "STATS"
        self.net.send(build_cmd("STATS", self.app_state.token, "ALL"))

    def on_selection_changed(self):
        rows = self.tbl_questions.selectedItems()
        if not rows:
            self.selected_qid = None
            self.btn_delete.setEnabled(False)
            return
        row = self.tbl_questions.currentRow()
        self.selected_qid = int(self.tbl_questions.item(row, 0).text())
        self.btn_delete.setEnabled(True)

    def do_add_question(self):
        dlg = AddQuestionDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            content, a, b, c, d, correct, diff, topic, expl = dlg.get_data()
            self.pending_cmd = "ADD_QUESTION"
            self.net.send(build_cmd("ADD_QUESTION", self.app_state.token, content, a, b, c, d, correct, diff, topic, expl))

    def do_delete_question(self):
        if not self.selected_qid:
            return
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa",
            f"Bạn có chắc muốn xóa câu hỏi #{self.selected_qid} khỏi ngân hàng?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.pending_cmd = "DEL_QUESTION"
            self.net.send(build_cmd("DEL_QUESTION", self.app_state.token, self.selected_qid))

    def do_import_csv(self):
        path, ok = QInputDialog.getText(
            self,
            "Import CSV",
            "Nhập đường dẫn file CSV trên server:",
            QLineEdit.Normal,
            "data/sample_questions.csv",
        )
        if ok and path.strip():
            self.pending_cmd = "IMPORT_CSV"
            self.net.send(build_cmd("IMPORT_CSV", self.app_state.token, path.strip()))

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
        if cmd == "LIST_QUESTIONS":
            if parts[0] == "OK":
                self.all_questions = []
                items = parts[1:] if len(parts) > 1 and parts[1] else []
                for item in items:
                    f = item.split(":")
                    if len(f) >= 5:
                        self.all_questions.append({
                            "qid": int(f[0]),
                            "content": unescape_field(f[1]),
                            "correct": int(f[2]),
                            "diff": f[3],
                            "topic": unescape_field(f[4]),
                        })
                self._apply_filter()

        elif cmd == "ADD_QUESTION":
            if parts[0] == "OK":
                QMessageBox.information(self, "Thành công", f"Đã thêm câu hỏi mới thành công (#{parts[1]})!")
                self.fetch_questions()

        elif cmd == "DEL_QUESTION":
            if parts[0] == "OK":
                QMessageBox.information(self, "Thành công", "Đã xóa câu hỏi thành công!")
                self.fetch_questions()

        elif cmd == "IMPORT_CSV":
            if parts[0] == "OK" and len(parts) >= 2:
                QMessageBox.information(self, "Thành công", f"Đã import thành công {parts[1]} câu hỏi từ CSV!")
                self.fetch_questions()

        elif cmd == "STATS":
            if parts[0] == "OK" and len(parts) >= 9:
                attempts = parts[1]
                avg_x100 = int(parts[2]) if parts[2].isdigit() else 0
                avg_pct = avg_x100 / 100.0

                self.lbl_sys_attempts.setText(f"Tổng lượt thi hệ thống: {attempts} lượt")
                self.lbl_sys_avg.setText(f"Điểm TB toàn hệ thống: {avg_pct:.1f}%")

                easy_c, easy_tot = int(parts[3]), int(parts[4])
                med_c, med_tot = int(parts[5]), int(parts[6])
                hard_c, hard_tot = int(parts[7]), int(parts[8])

                self._render_stats_bars(easy_c, easy_tot, med_c, med_tot, hard_c, hard_tot)

    def _apply_filter(self):
        flt = self.cmb_filter_diff.currentText()
        filtered = [q for q in self.all_questions if flt == "Tất cả" or q["diff"] == flt]

        self.tbl_questions.setRowCount(0)
        self.tbl_questions.setRowCount(len(filtered))
        opts_labels = ["A", "B", "C", "D"]

        for r, q in enumerate(filtered):
            self.tbl_questions.setItem(r, 0, QTableWidgetItem(str(q["qid"])))
            self.tbl_questions.setItem(r, 1, QTableWidgetItem(q["content"]))
            self.tbl_questions.setItem(r, 2, QTableWidgetItem(opts_labels[q["correct"]] if 0 <= q["correct"] < 4 else str(q["correct"])))
            self.tbl_questions.setItem(r, 3, QTableWidgetItem(q["diff"]))
            self.tbl_questions.setItem(r, 4, QTableWidgetItem(q["topic"]))

        self.btn_delete.setEnabled(False)

    def _render_stats_bars(self, easy_c, easy_tot, med_c, med_tot, hard_c, hard_tot):
        while self.layout_stats_bars.count():
            item = self.layout_stats_bars.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        diffs = [
            ("Độ khó Dễ", easy_c, easy_tot, "#10b981"),
            ("Trung bình", med_c, med_tot, "#38bdf8"),
            ("Độ khó Khó", hard_c, hard_tot, "#f43f5e"),
        ]
        for name, c, tot, color in diffs:
            pct = int((c / tot * 100)) if tot > 0 else 0
            row = QHBoxLayout()
            lbl = QLabel(f"{name} ({c}/{tot}):")
            lbl.setFixedWidth(140)
            lbl.setStyleSheet("color: #cbd5e1; font-weight: 600; font-size: 12px;")

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
                    height: 20px;
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                    border-radius: 5px;
                }}
            """)
            row.addWidget(lbl)
            row.addWidget(bar)
            self.layout_stats_bars.addLayout(row)
