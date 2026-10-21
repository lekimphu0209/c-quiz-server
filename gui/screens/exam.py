from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QRadioButton,
    QButtonGroup,
    QMessageBox,
    QFrame,
    QScrollArea,
)
from proto import build_cmd, parse_err, unescape_field
from widgets import QuestionMatrix, CountdownLabel


class ExamScreen(QWidget):
    """Exam & Practice interactive taking screen (S5)."""

    def __init__(self, app_state, net, goto_callback, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.net = net
        self.goto = goto_callback
        self.pending_cmd = None

        self.current_q = 1
        self.total_q = 0
        self.questions = []
        self.answers = []
        self._updating_radios = False

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 24)
        layout.setSpacing(16)

        # Top Bar: Title, Timer, and Submit Button
        top_bar = QHBoxLayout()
        self.lbl_exam_title = QLabel("BÀI THI TRỰC TUYẾN")
        self.lbl_exam_title.setProperty("heading", "true")

        self.timer_label = CountdownLabel(600)
        self.timer_label.time_up.connect(self.on_time_up)

        self.btn_submit = QPushButton("⚑ NỘP BÀI")
        self.btn_submit.setProperty("success", "true")
        self.btn_submit.setFixedSize(130, 42)
        self.btn_submit.setStyleSheet(
            "background-color: #10b981; color: white; font-weight: 800; font-size: 14px; border-radius: 8px;"
        )
        self.btn_submit.clicked.connect(self.do_submit)

        top_bar.addWidget(self.lbl_exam_title)
        top_bar.addStretch()
        top_bar.addWidget(self.timer_label)
        top_bar.addSpacing(16)
        top_bar.addWidget(self.btn_submit)
        layout.addLayout(top_bar)

        # Main Split Content
        main_content = QHBoxLayout()
        main_content.setSpacing(20)

        # Left Column: Question Matrix
        left_box = QFrame()
        left_box.setProperty("card", "true")
        left_box.setFixedWidth(270)
        left_layout = QVBoxLayout(left_box)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        lbl_matrix_title = QLabel("MA TRẬN CÂU HỎI")
        lbl_matrix_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #cbd5e1;")
        left_layout.addWidget(lbl_matrix_title)

        matrix_scroll = QScrollArea()
        matrix_scroll.setWidgetResizable(True)
        matrix_scroll.setStyleSheet("background: transparent; border: none;")

        self.matrix = QuestionMatrix(10)
        self.matrix.question_clicked.connect(self.show_question)
        matrix_scroll.setWidget(self.matrix)
        left_layout.addWidget(matrix_scroll, stretch=1)

        # Legend
        legend_layout = QHBoxLayout()
        legend_layout.setSpacing(10)
        lbl_ans = QLabel("🟩 Đã làm")
        lbl_ans.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 600;")
        lbl_unans = QLabel("⬛ Chưa làm")
        lbl_unans.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        legend_layout.addWidget(lbl_ans)
        legend_layout.addWidget(lbl_unans)
        legend_layout.addStretch()
        left_layout.addLayout(legend_layout)

        self.lbl_progress = QLabel("Đã làm: 0/0 câu")
        self.lbl_progress.setStyleSheet("font-size: 13px; font-weight: 700; color: #38bdf8;")
        left_layout.addWidget(self.lbl_progress)

        main_content.addWidget(left_box)

        # Right Column: Question Content & Options
        right_box = QFrame()
        right_box.setProperty("card", "true")
        right_layout = QVBoxLayout(right_box)
        right_layout.setContentsMargins(28, 24, 28, 24)
        right_layout.setSpacing(18)

        # Question Index & Difficulty Header
        q_header = QHBoxLayout()
        self.lbl_q_idx = QLabel("Câu 1 / 10")
        self.lbl_q_idx.setStyleSheet("font-size: 18px; font-weight: 800; color: #f8fafc;")

        self.lbl_diff_badge = QLabel("Trung bình")
        self.lbl_diff_badge.setStyleSheet(
            "background-color: rgba(56, 189, 248, 0.2); color: #38bdf8; "
            "padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700;"
        )

        q_header.addWidget(self.lbl_q_idx)
        q_header.addSpacing(10)
        q_header.addWidget(self.lbl_diff_badge)
        q_header.addStretch()
        right_layout.addLayout(q_header)

        # Question Text Box
        self.lbl_content = QLabel("Nội dung câu hỏi đang được tải...")
        self.lbl_content.setWordWrap(True)
        self.lbl_content.setStyleSheet(
            "font-size: 15px; font-weight: 600; color: #f1f5f9; line-height: 1.5; "
            "background-color: #0f172a; padding: 16px; border: 1px solid #334155; border-radius: 8px;"
        )
        right_layout.addWidget(self.lbl_content)

        # Options Radio Group
        self.opt_group = QButtonGroup(self)
        self.radio_opts = []
        labels = ["A", "B", "C", "D"]

        opts_container = QVBoxLayout()
        opts_container.setSpacing(12)

        for i, letter in enumerate(labels):
            rdo = QRadioButton(f"{letter}. Đang tải...")
            rdo.setCursor(Qt.PointingHandCursor)
            rdo.setStyleSheet("""
                QRadioButton {
                    font-size: 14px;
                    font-weight: 500;
                    color: #e2e8f0;
                    padding: 10px 14px;
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 8px;
                }
                QRadioButton:hover {
                    background-color: #273549;
                    border-color: #6366f1;
                }
                QRadioButton:checked {
                    background-color: rgba(99, 102, 241, 0.2);
                    border: 2px solid #6366f1;
                    color: #ffffff;
                    font-weight: 700;
                }
            """)
            self.opt_group.addButton(rdo, i)
            opts_container.addWidget(rdo)
            self.radio_opts.append(rdo)

        self.opt_group.buttonClicked[int].connect(self.on_option_clicked)
        right_layout.addLayout(opts_container)
        right_layout.addStretch()

        # Prev / Next Navigation Row
        nav_row = QHBoxLayout()
        self.btn_prev = QPushButton("◀ Câu trước")
        self.btn_prev.setProperty("secondary", "true")
        self.btn_prev.setFixedSize(130, 40)
        self.btn_prev.clicked.connect(self.go_prev)

        self.btn_next = QPushButton("Câu sau ▶")
        self.btn_next.setProperty("secondary", "true")
        self.btn_next.setFixedSize(130, 40)
        self.btn_next.clicked.connect(self.go_next)

        nav_row.addWidget(self.btn_prev)
        nav_row.addStretch()
        nav_row.addWidget(self.btn_next)
        right_layout.addLayout(nav_row)

        main_content.addWidget(right_box, stretch=1)
        layout.addLayout(main_content)

    def on_enter(self):
        self.pending_cmd = None
        exam = getattr(self.app_state, "exam", {})
        if not exam:
            return

        rid = exam.get("rid", 0)
        mode = exam.get("mode", "room")
        self.total_q = exam.get("n", 0)
        sec = exam.get("sec", 600)
        self.questions = exam.get("questions", [])

        # Reset or restore answers array (1-indexed)
        if "answers" not in exam or len(exam["answers"]) != self.total_q + 1:
            self.answers = [-1] * (self.total_q + 1)
            exam["answers"] = self.answers
        else:
            self.answers = exam["answers"]

        if mode == "practice":
            self.lbl_exam_title.setText(f"LUYỆN TẬP CÁ NHÂN (#{rid})")
        else:
            rname = getattr(self.app_state, "room_name", f"Phòng #{rid}")
            self.lbl_exam_title.setText(f"BÀI THI: {rname}")

        self.matrix.set_count(self.total_q)
        for i in range(1, self.total_q + 1):
            if self.answers[i] != -1:
                self.matrix.set_answered(i, True)

        self.timer_label.start_countdown(sec)
        self.current_q = 1
        self.show_question(1)
        self._update_progress_label()

    def on_leave(self):
        self.timer_label.stop_countdown()
        self.pending_cmd = None

    def show_question(self, q_idx: int):
        if q_idx < 1 or q_idx > self.total_q or not self.questions:
            return

        self.current_q = q_idx
        self.matrix.set_current(q_idx)

        q = self.questions[q_idx - 1]
        self.lbl_q_idx.setText(f"Câu {q_idx} / {self.total_q}")

        diff = q.get("difficulty", "medium")
        diff_text = {"easy": "Dễ", "medium": "Trung bình", "hard": "Khó"}.get(diff, diff)
        self.lbl_diff_badge.setText(diff_text)
        if diff == "easy":
            self.lbl_diff_badge.setStyleSheet("background-color: rgba(16, 185, 129, 0.2); color: #34d399; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700;")
        elif diff == "hard":
            self.lbl_diff_badge.setStyleSheet("background-color: rgba(239, 68, 68, 0.2); color: #f87171; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700;")
        else:
            self.lbl_diff_badge.setStyleSheet("background-color: rgba(56, 189, 248, 0.2); color: #38bdf8; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700;")

        self.lbl_content.setText(q.get("content", ""))

        self._updating_radios = True
        self.radio_opts[0].setText(f"A. {q.get('opt_a', '')}")
        self.radio_opts[1].setText(f"B. {q.get('opt_b', '')}")
        self.radio_opts[2].setText(f"C. {q.get('opt_c', '')}")
        self.radio_opts[3].setText(f"D. {q.get('opt_d', '')}")

        ans = self.answers[q_idx]
        self.opt_group.setExclusive(False)
        for i in range(4):
            self.radio_opts[i].setChecked(i == ans)
        self.opt_group.setExclusive(True)
        self._updating_radios = False

        self.btn_prev.setEnabled(q_idx > 1)
        self.btn_next.setEnabled(q_idx < self.total_q)

    def on_option_clicked(self, opt_idx: int):
        if self._updating_radios:
            return

        if self.answers[self.current_q] == opt_idx:
            return

        self.answers[self.current_q] = opt_idx
        self.matrix.set_answered(self.current_q, True)
        self._update_progress_label()

        # Send immediate ANSWER command to server (qidx is 1-indexed)
        rid = self.app_state.exam.get("rid", 0)
        self.net.send(build_cmd("ANSWER", self.app_state.token, rid, self.current_q, opt_idx))

    def _update_progress_label(self):
        answered_count = sum(1 for a in self.answers[1:self.total_q + 1] if a != -1)
        self.lbl_progress.setText(f"Đã làm: {answered_count}/{self.total_q} câu")

    def go_prev(self):
        if self.current_q > 1:
            self.show_question(self.current_q - 1)

    def go_next(self):
        if self.current_q < self.total_q:
            self.show_question(self.current_q + 1)

    def do_submit(self):
        answered_count = sum(1 for a in self.answers[1:self.total_q + 1] if a != -1)
        rem = self.total_q - answered_count

        msg = f"Bạn còn {rem} câu chưa trả lời. Bạn có chắc chắn muốn nộp bài ngay bây giờ?" if rem > 0 else "Bạn đã làm đủ tất cả các câu. Bạn có chắc chắn muốn nộp bài?"
        reply = QMessageBox.question(self, "Xác nhận nộp bài", msg, QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._send_submit()

    def _send_submit(self):
        mode = self.app_state.exam.get("mode", "room")
        rid = self.app_state.exam.get("rid", 0)
        cmd_name = "PRACTICE_SUBMIT" if mode == "practice" else "SUBMIT"
        self.pending_cmd = cmd_name
        self.net.send(build_cmd(cmd_name, self.app_state.token, rid))

    def on_time_up(self):
        for rdo in self.radio_opts:
            rdo.setEnabled(False)
        self.btn_submit.setEnabled(False)
        QMessageBox.information(self, "Hết giờ làm bài", "Đã hết giờ làm bài thi! Hệ thống đang tự động nộp bài.")
        self._send_submit()

    def on_response(self, payload: str):
        if not self.pending_cmd:
            return

        cmd = self.pending_cmd
        self.pending_cmd = None

        if payload.startswith("ERR|"):
            code, friendly_msg = parse_err(payload)
            if code == "EXAM_ENDED" or code == "ALREADY_SUBMITTED":
                self.goto("result")
            else:
                QMessageBox.warning(self, "Thông báo lỗi", friendly_msg)
            return

        parts = payload.split("|")
        if cmd in ("SUBMIT", "PRACTICE_SUBMIT"):
            if parts[0] == "OK" and len(parts) >= 3:
                score = int(parts[1])
                total = int(parts[2])
                self.app_state.last_result = {
                    "score": score,
                    "total": total,
                    "rank": "-",
                    "rid": self.app_state.exam.get("rid", 0),
                    "mode": self.app_state.exam.get("mode", "room"),
                }
                self.goto("result")

    def handle_event(self, payload: str):
        parts = payload.split("|")
        if len(parts) < 3:
            return

        evt_type = parts[1]
        evt_rid = int(parts[2]) if parts[2].isdigit() else -1

        if evt_rid != self.app_state.exam.get("rid", -1):
            return

        if evt_type == "RESULT" and len(parts) >= 5:
            # EVT|RESULT|rid|score/total|rank
            score_total = parts[3].split("/")
            score = int(score_total[0]) if len(score_total) > 0 and score_total[0].isdigit() else 0
            total = int(score_total[1]) if len(score_total) > 1 and score_total[1].isdigit() else self.total_q
            rank = parts[4]

            self.app_state.last_result = {
                "score": score,
                "total": total,
                "rank": rank,
                "rid": evt_rid,
                "mode": self.app_state.exam.get("mode", "room"),
            }
            self.goto("result")

        elif evt_type == "TICK" and len(parts) >= 4:
            sec = int(parts[3]) if parts[3].isdigit() else 0
            self.timer_label.set_remain(sec)
