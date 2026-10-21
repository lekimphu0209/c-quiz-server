from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QFrame,
)
from proto import build_cmd, parse_err, parse_exam_body, unescape_field


class WaitingScreen(QWidget):
    """Waiting lobby screen (S4) with dynamic Host and Participant views."""

    def __init__(self, app_state, net, goto_callback, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.net = net
        self.goto = goto_callback
        self.pending_cmd = None
        self.members = []

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 36)
        layout.setSpacing(20)

        # Header bar
        header = QHBoxLayout()
        self.btn_back = QPushButton("← Rời phòng")
        self.btn_back.setProperty("secondary", "true")
        self.btn_back.setFixedWidth(130)
        self.btn_back.clicked.connect(self.do_leave)

        self.lbl_title = QLabel("PHÒNG THI CHỜ BẮT ĐẦU")
        self.lbl_title.setProperty("heading", "true")

        self.lbl_role_badge = QLabel("Chủ phòng")
        self.lbl_role_badge.setStyleSheet(
            "background-color: rgba(99, 102, 241, 0.2); color: #818cf8; "
            "padding: 4px 12px; border-radius: 9999px; font-weight: 700; font-size: 12px;"
        )

        header.addWidget(self.btn_back)
        header.addSpacing(12)
        header.addWidget(self.lbl_title)
        header.addSpacing(8)
        header.addWidget(self.lbl_role_badge)
        header.addStretch()
        layout.addLayout(header)

        # Card: Room Metadata Info
        info_card = QFrame()
        info_card.setProperty("card", "true")
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(24, 20, 24, 20)
        info_layout.setSpacing(8)

        self.lbl_room_name = QLabel("Phòng: Đang tải...")
        self.lbl_room_name.setStyleSheet("font-size: 18px; font-weight: 700; color: #f8fafc;")

        self.lbl_room_details = QLabel("20 câu • 30 phút • Độ khó: mixed • Chủ: ...")
        self.lbl_room_details.setStyleSheet("font-size: 13px; color: #94a3b8;")

        info_layout.addWidget(self.lbl_room_name)
        info_layout.addWidget(self.lbl_room_details)
        layout.addWidget(info_card)

        # Members Section
        members_box = QFrame()
        members_box.setProperty("card", "true")
        m_layout = QVBoxLayout(members_box)
        m_layout.setContentsMargins(24, 20, 24, 20)
        m_layout.setSpacing(12)

        self.lbl_members_count = QLabel("Thí sinh trong phòng (0/20):")
        self.lbl_members_count.setStyleSheet("font-size: 14px; font-weight: 700; color: #e2e8f0;")
        m_layout.addWidget(self.lbl_members_count)

        self.lst_members = QListWidget()
        self.lst_members.setStyleSheet(
            "QListWidget { background-color: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 6px; } "
            "QListWidget::item { padding: 10px 14px; border-bottom: 1px solid #1e293b; color: #e2e8f0; font-size: 13px; font-weight: 600; } "
            "QListWidget::item:selected { background-color: #312e81; color: #ffffff; }"
        )
        m_layout.addWidget(self.lst_members)
        layout.addWidget(members_box, stretch=1)

        # Actions Panel (Host View vs Participant View)
        self.actions_panel = QFrame()
        self.actions_panel.setProperty("card", "true")
        p_layout = QVBoxLayout(self.actions_panel)
        p_layout.setContentsMargins(24, 20, 24, 20)
        p_layout.setSpacing(12)

        # Host Controls
        self.host_box = QWidget()
        h_layout = QHBoxLayout(self.host_box)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(16)

        self.btn_cancel = QPushButton("✖ HỦY PHÒNG")
        self.btn_cancel.setProperty("danger", "true")
        self.btn_cancel.setFixedWidth(160)
        self.btn_cancel.clicked.connect(self.do_leave)

        self.btn_start = QPushButton("▶ BẮT ĐẦU THI")
        self.btn_start.setProperty("success", "true")
        self.btn_start.setFixedHeight(46)
        self.btn_start.setStyleSheet(
            "background-color: #10b981; color: white; font-weight: 800; font-size: 15px; border-radius: 8px;"
        )
        self.btn_start.clicked.connect(self.do_start_exam)

        h_layout.addWidget(self.btn_cancel)
        h_layout.addWidget(self.btn_start, stretch=1)
        p_layout.addWidget(self.host_box)

        # Participant Controls
        self.participant_box = QWidget()
        part_layout = QVBoxLayout(self.participant_box)
        part_layout.setContentsMargins(0, 0, 0, 0)
        part_layout.setSpacing(10)

        self.lbl_participant_wait = QLabel("⏳ Đang chờ chủ phòng bắt đầu bài thi...")
        self.lbl_participant_wait.setAlignment(Qt.AlignCenter)
        self.lbl_participant_wait.setStyleSheet(
            "font-size: 14px; font-weight: 600; color: #38bdf8; padding: 10px;"
        )

        self.btn_part_leave = QPushButton("🚪 RỜI PHÒNG THI")
        self.btn_part_leave.setProperty("secondary", "true")
        self.btn_part_leave.setFixedHeight(40)
        self.btn_part_leave.clicked.connect(self.do_leave)

        part_layout.addWidget(self.lbl_participant_wait)
        part_layout.addWidget(self.btn_part_leave)
        p_layout.addWidget(self.participant_box)

        layout.addWidget(self.actions_panel)

    def on_enter(self):
        self.pending_cmd = None
        rid = self.app_state.room_id
        name = getattr(self.app_state, "room_name", f"Phòng #{rid}")
        owner = getattr(self.app_state, "room_owner", "")
        meta = getattr(self.app_state, "room_meta", {})

        n = meta.get("n", 20)
        sec = meta.get("sec", 1800)
        diff = meta.get("diff", "mixed")
        initial_mems = meta.get("members", [])

        is_host = (self.app_state.username == owner)
        self.lbl_role_badge.setText("Chủ phòng" if is_host else "Thí sinh")
        self.lbl_role_badge.setStyleSheet(
            "background-color: rgba(99, 102, 241, 0.2); color: #818cf8; padding: 4px 12px; border-radius: 9999px; font-weight: 700; font-size: 12px;"
            if is_host else
            "background-color: rgba(16, 185, 129, 0.2); color: #34d399; padding: 4px 12px; border-radius: 9999px; font-weight: 700; font-size: 12px;"
        )

        self.host_box.setVisible(is_host)
        self.participant_box.setVisible(not is_host)

        self.lbl_room_name.setText(f"Phòng #{rid}: {name}")
        mins = int(sec) // 60
        self.lbl_room_details.setText(f"{n} câu hỏi • {mins} phút ({sec}s) • Độ khó: {diff} • Chủ phòng: {owner}")

        self.members = list(initial_mems)
        if self.app_state.username not in self.members:
            self.members.append(self.app_state.username)
        self._refresh_members_list()

    def on_leave(self):
        self.pending_cmd = None

    def _refresh_members_list(self):
        self.lst_members.clear()
        owner = getattr(self.app_state, "room_owner", "")
        self.lbl_members_count.setText(f"Thí sinh trong phòng ({len(self.members)}/20):")

        for u in self.members:
            tag = ""
            if u == owner and u == self.app_state.username:
                tag = " (Bạn - Chủ phòng)"
            elif u == owner:
                tag = " (Chủ phòng)"
            elif u == self.app_state.username:
                tag = " (Bạn)"

            item = QListWidgetItem(f"👤  {u}{tag}")
            self.lst_members.addItem(item)

        # Host start button validation: needs at least 2 participants per project spec
        if self.app_state.username == owner:
            can_start = len(self.members) >= 2
            self.btn_start.setEnabled(can_start)
            if can_start:
                self.btn_start.setText("▶ BẮT ĐẦU THI")
                self.btn_start.setStyleSheet(
                    "background-color: #10b981; color: white; font-weight: 800; font-size: 15px; border-radius: 8px;"
                )
            else:
                self.btn_start.setText("▶ BẮT ĐẦU THI (Cần ít nhất 2 thí sinh)")
                self.btn_start.setStyleSheet(
                    "background-color: #334155; color: #94a3b8; font-weight: 800; font-size: 13px; border-radius: 8px;"
                )

    def do_leave(self):
        is_host = (self.app_state.username == getattr(self.app_state, "room_owner", ""))
        msg = "Bạn là chủ phòng. Rời phòng sẽ HỦY phòng thi đối với mọi người. Bạn có chắc không?" if is_host else "Bạn có chắc chắn muốn rời phòng thi này?"
        reply = QMessageBox.question(self, "Xác nhận rời phòng", msg, QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.pending_cmd = "LEAVE_ROOM"
            self.net.send(build_cmd("LEAVE_ROOM", self.app_state.token, self.app_state.room_id))

    def do_start_exam(self):
        if len(self.members) < 2:
            QMessageBox.warning(self, "Thông báo", "Cần có ít nhất 2 thí sinh trong phòng để bắt đầu thi!")
            return
        self.pending_cmd = "START_ROOM"
        self.net.send(build_cmd("START_ROOM", self.app_state.token, self.app_state.room_id))

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
        if cmd == "LEAVE_ROOM":
            if parts[0] == "OK":
                self.app_state.room_id = None
                self.goto("lobby")

        elif cmd == "START_ROOM":
            if parts[0] == "OK" and len(parts) >= 6:
                # OK|STARTED|rid|n|sec|qrec...
                rid = int(parts[2])
                n = int(parts[3])
                sec = int(parts[4])
                questions = parse_exam_body(parts, start_idx=5)
                self.app_state.exam = {
                    "rid": rid,
                    "n": n,
                    "sec": sec,
                    "questions": questions,
                    "answers": [-1] * (n + 1),
                    "mode": "room",
                }
                self.goto("exam")

    def handle_event(self, payload: str):
        parts = payload.split("|")
        if len(parts) < 3:
            return

        evt_type = parts[1]
        evt_rid = int(parts[2]) if parts[2].isdigit() else -1

        if evt_rid != self.app_state.room_id:
            return

        if evt_type == "MEMBER_JOINED" and len(parts) >= 4:
            new_user = parts[3]
            if new_user not in self.members:
                self.members.append(new_user)
                self._refresh_members_list()

        elif evt_type == "MEMBER_LEFT" and len(parts) >= 4:
            left_user = parts[3]
            if left_user in self.members:
                self.members.remove(left_user)
                self._refresh_members_list()

        elif evt_type == "ROOM_CLOSED":
            QMessageBox.information(self, "Thông báo", "Chủ phòng đã hủy phòng thi.")
            self.app_state.room_id = None
            self.goto("lobby")

        elif evt_type == "EXAM" and len(parts) >= 6:
            # EVT|EXAM|rid|n|sec|qrec...
            rid = int(parts[2])
            n = int(parts[3])
            sec = int(parts[4])
            questions = parse_exam_body(parts, start_idx=5)
            self.app_state.exam = {
                "rid": rid,
                "n": n,
                "sec": sec,
                "questions": questions,
                "answers": [-1] * (n + 1),
                "mode": "room",
            }
            self.goto("exam")
