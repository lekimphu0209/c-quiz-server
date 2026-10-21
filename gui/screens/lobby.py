from PyQt5.QtCore import Qt, QTimer
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
    QDialog,
    QLineEdit,
    QSpinBox,
    QMessageBox,
    QFrame,
)
from proto import build_cmd, parse_err, unescape_field
from widgets import StatusBadge


class CreateRoomDialog(QDialog):
    """Dialog for creating a new exam room."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tạo phòng thi mới")
        self.setFixedSize(440, 420)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        card = QFrame()
        card.setProperty("card", "true")
        form = QVBoxLayout(card)
        form.setSpacing(10)

        # Name
        form.addWidget(QLabel("Tên phòng thi (1-50 ký tự):"))
        self.ed_name = QLineEdit()
        self.ed_name.setPlaceholderText("VD: Thi giữa kỳ Lập trình mạng")
        form.addWidget(self.ed_name)

        # Count & Sec
        row1 = QHBoxLayout()
        v_n = QVBoxLayout()
        v_n.addWidget(QLabel("Số câu hỏi:"))
        self.spn_n = QSpinBox()
        self.spn_n.setRange(1, 100)
        self.spn_n.setValue(20)
        self.spn_n.valueChanged.connect(self._sync_diff_totals)
        v_n.addWidget(self.spn_n)

        v_sec = QVBoxLayout()
        v_sec.addWidget(QLabel("Thời gian (giây):"))
        self.spn_sec = QSpinBox()
        self.spn_sec.setRange(60, 14400)
        self.spn_sec.setValue(1800)
        self.spn_sec.setSingleStep(60)
        v_sec.addWidget(self.spn_sec)

        row1.addLayout(v_n)
        row1.addLayout(v_sec)
        form.addLayout(row1)

        # Difficulty breakdown
        form.addWidget(QLabel("Tỷ lệ câu hỏi (Dễ / TB / Khó):"))
        diff_row = QHBoxLayout()
        self.spn_easy = QSpinBox()
        self.spn_easy.setRange(0, 100)
        self.spn_easy.setValue(5)
        self.spn_easy.valueChanged.connect(self._check_ratio)

        self.spn_med = QSpinBox()
        self.spn_med.setRange(0, 100)
        self.spn_med.setValue(10)
        self.spn_med.valueChanged.connect(self._check_ratio)

        self.spn_hard = QSpinBox()
        self.spn_hard.setRange(0, 100)
        self.spn_hard.setValue(5)
        self.spn_hard.valueChanged.connect(self._check_ratio)

        diff_row.addWidget(QLabel("Dễ:"))
        diff_row.addWidget(self.spn_easy)
        diff_row.addWidget(QLabel("TB:"))
        diff_row.addWidget(self.spn_med)
        diff_row.addWidget(QLabel("Khó:"))
        diff_row.addWidget(self.spn_hard)
        form.addLayout(diff_row)

        self.lbl_ratio_hint = QLabel("Tổng tỷ lệ: 20 / 20")
        self.lbl_ratio_hint.setStyleSheet("color: #10b981; font-size: 11px;")
        form.addWidget(self.lbl_ratio_hint)

        # Topic
        form.addWidget(QLabel("Chủ đề:"))
        self.cmb_topic = QComboBox()
        self.cmb_topic.addItems(["all", "net", "c", "os"])
        form.addWidget(self.cmb_topic)

        layout.addWidget(card)

        # Buttons
        btn_box = QHBoxLayout()
        self.btn_create = QPushButton("TẠO PHÒNG")
        self.btn_create.setProperty("success", "true")
        self.btn_create.clicked.connect(self.validate_and_accept)

        self.btn_cancel = QPushButton("HỦY")
        self.btn_cancel.setProperty("secondary", "true")
        self.btn_cancel.clicked.connect(self.reject)

        btn_box.addWidget(self.btn_create)
        btn_box.addWidget(self.btn_cancel)
        layout.addLayout(btn_box)

    def _sync_diff_totals(self, val):
        e = val // 4
        h = val // 4
        m = val - e - h
        self.spn_easy.setValue(e)
        self.spn_med.setValue(m)
        self.spn_hard.setValue(h)
        self._check_ratio()

    def _check_ratio(self):
        total = self.spn_easy.value() + self.spn_med.value() + self.spn_hard.value()
        needed = self.spn_n.value()
        if total == needed:
            self.lbl_ratio_hint.setText(f"✓ Tổng tỷ lệ: {total} / {needed} (Khớp)")
            self.lbl_ratio_hint.setStyleSheet("color: #10b981; font-weight: 700; font-size: 11px;")
        else:
            self.lbl_ratio_hint.setText(f"⚠ Tổng tỷ lệ: {total} / {needed} (Chưa khớp)")
            self.lbl_ratio_hint.setStyleSheet("color: #ef4444; font-weight: 700; font-size: 11px;")

    def validate_and_accept(self):
        name = self.ed_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập tên phòng thi (1-50 ký tự).")
            return
        total = self.spn_easy.value() + self.spn_med.value() + self.spn_hard.value()
        if total != self.spn_n.value():
            QMessageBox.warning(self, "Lỗi", "Tổng số câu hỏi Dễ + TB + Khó phải bằng đúng tổng số câu hỏi của đề.")
            return
        self.accept()

    def get_data(self):
        diff_str = f"easy:{self.spn_easy.value()},medium:{self.spn_med.value()},hard:{self.spn_hard.value()}"
        return (
            self.ed_name.text().strip(),
            self.spn_n.value(),
            self.spn_sec.value(),
            diff_str,
            self.cmb_topic.currentText(),
        )


class LobbyScreen(QWidget):
    def __init__(self, app_state, net, goto_callback, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.net = net
        self.goto = goto_callback
        self.pending_cmd = None
        self.selected_room = None

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(5000)
        self.refresh_timer.timeout.connect(self.refresh_rooms)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 32)
        layout.setSpacing(18)

        # Header Navigation
        header = QHBoxLayout()
        self.btn_back = QPushButton("← Trang chủ")
        self.btn_back.setProperty("secondary", "true")
        self.btn_back.setFixedWidth(120)
        self.btn_back.clicked.connect(lambda: self.goto("dashboard"))

        lbl_title = QLabel("SẢNH PHÒNG THI TRỰC TUYẾN")
        lbl_title.setProperty("heading", "true")

        self.btn_refresh = QPushButton("🔄 Làm mới")
        self.btn_refresh.setProperty("secondary", "true")
        self.btn_refresh.setFixedWidth(110)
        self.btn_refresh.clicked.connect(self.refresh_rooms)

        header.addWidget(self.btn_back)
        header.addSpacing(12)
        header.addWidget(lbl_title)
        header.addStretch()
        header.addWidget(self.btn_refresh)
        layout.addLayout(header)

        # Filter Bar
        filter_bar = QHBoxLayout()
        filter_bar.addWidget(QLabel("Lọc trạng thái:"))
        self.cmb_filter = QComboBox()
        self.cmb_filter.addItems(["ALL", "WAITING", "RUNNING", "FINISHED"])
        self.cmb_filter.currentIndexChanged.connect(self.refresh_rooms)
        self.cmb_filter.setFixedWidth(140)
        filter_bar.addWidget(self.cmb_filter)
        filter_bar.addStretch()

        self.btn_create = QPushButton("＋ TẠO PHÒNG MỚI")
        self.btn_create.setProperty("success", "true")
        self.btn_create.clicked.connect(self.do_create_room)
        filter_bar.addWidget(self.btn_create)

        layout.addLayout(filter_bar)

        # Rooms Table
        self.tbl_rooms = QTableWidget()
        self.tbl_rooms.setColumnCount(7)
        self.tbl_rooms.setHorizontalHeaderLabels([
            "ID", "Tên phòng", "Chủ phòng", "Trạng thái", "Số câu", "Thời gian (s)", "Thí sinh"
        ])
        self.tbl_rooms.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_rooms.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl_rooms.setSelectionMode(QTableWidget.SingleSelection)
        self.tbl_rooms.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_rooms.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.tbl_rooms)

        # Action Buttons
        actions_bar = QHBoxLayout()
        self.btn_join = QPushButton("▶ THAM GIA PHÒNG")
        self.btn_join.setEnabled(False)
        self.btn_join.clicked.connect(self.do_join_room)

        self.btn_result = QPushButton("📊 XEM KẾT QUẢ")
        self.btn_result.setProperty("secondary", "true")
        self.btn_result.setEnabled(False)
        self.btn_result.clicked.connect(self.do_view_result)

        actions_bar.addStretch()
        actions_bar.addWidget(self.btn_join)
        actions_bar.addWidget(self.btn_result)
        layout.addLayout(actions_bar)

    def on_enter(self):
        self.pending_cmd = None
        self.selected_room = None
        self.btn_join.setEnabled(False)
        self.btn_result.setEnabled(False)
        self.refresh_rooms()
        self.refresh_timer.start()

    def on_leave(self):
        self.refresh_timer.stop()
        self.pending_cmd = None

    def refresh_rooms(self):
        flt = self.cmb_filter.currentText()
        self.pending_cmd = "LIST_ROOMS"
        self.net.send(build_cmd("LIST_ROOMS", self.app_state.token, flt))

    def on_selection_changed(self):
        rows = self.tbl_rooms.selectedItems()
        if not rows:
            self.selected_room = None
            self.btn_join.setEnabled(False)
            self.btn_result.setEnabled(False)
            return

        row = self.tbl_rooms.currentRow()
        rid = int(self.tbl_rooms.item(row, 0).text())
        name = self.tbl_rooms.item(row, 1).text()
        owner = self.tbl_rooms.item(row, 2).text()
        badge_widget = self.tbl_rooms.cellWidget(row, 3)
        status = badge_widget.lbl_text.text() if badge_widget else "WAITING"

        self.selected_room = {"rid": rid, "name": name, "owner": owner, "status": status}
        self.btn_join.setEnabled(status == "WAITING")
        self.btn_result.setEnabled(status == "FINISHED")

    def do_create_room(self):
        dlg = CreateRoomDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            name, n, sec, diff, topic = dlg.get_data()
            self._last_created = {
                "name": name,
                "n": n,
                "sec": sec,
                "diff": diff,
                "topic": topic,
            }
            self.pending_cmd = "CREATE_ROOM"
            self.net.send(build_cmd("CREATE_ROOM", self.app_state.token, name, n, sec, diff, topic))

    def do_join_room(self):
        if not self.selected_room:
            return
        rid = self.selected_room["rid"]
        self.pending_cmd = "JOIN"
        self.net.send(build_cmd("JOIN", self.app_state.token, rid))

    def do_view_result(self):
        if not self.selected_room:
            return
        rid = self.selected_room["rid"]
        self.app_state.room_id = rid
        self.app_state.room_name = self.selected_room["name"]
        self.pending_cmd = "ROOM_RESULT"
        self.net.send(build_cmd("ROOM_RESULT", self.app_state.token, rid))

    def on_response(self, payload: str):
        if not self.pending_cmd:
            return

        cmd = self.pending_cmd
        self.pending_cmd = None

        if payload.startswith("ERR|"):
            _, friendly_msg = parse_err(payload)
            QMessageBox.warning(self, "Thông báo", friendly_msg)
            self.refresh_rooms()
            return

        parts = payload.split("|")
        if cmd == "LIST_ROOMS":
            # OK|room1|room2... where room = rid:name:owner:status:n:sec:mem
            self.tbl_rooms.setRowCount(0)
            items = parts[1:] if len(parts) > 1 and parts[1] else []
            self.tbl_rooms.setRowCount(len(items))

            for row_idx, item in enumerate(items):
                fields = item.split(":")
                if len(fields) < 7:
                    continue
                rid, name, owner, status, n, sec, mem = fields[:7]

                self.tbl_rooms.setItem(row_idx, 0, QTableWidgetItem(rid))
                self.tbl_rooms.setItem(row_idx, 1, QTableWidgetItem(unescape_field(name)))
                self.tbl_rooms.setItem(row_idx, 2, QTableWidgetItem(owner))

                badge = StatusBadge(status)
                self.tbl_rooms.setCellWidget(row_idx, 3, badge)

                self.tbl_rooms.setItem(row_idx, 4, QTableWidgetItem(n))
                self.tbl_rooms.setItem(row_idx, 5, QTableWidgetItem(sec))
                self.tbl_rooms.setItem(row_idx, 6, QTableWidgetItem(f"{mem} / 20"))

        elif cmd == "CREATE_ROOM":
            if parts[0] == "OK" and len(parts) >= 2:
                rid = int(parts[1])
                self.app_state.room_id = rid
                self.app_state.room_owner = self.app_state.username
                created = getattr(self, "_last_created", {})
                self.app_state.room_name = created.get("name", f"Phòng #{rid}")
                self.app_state.room_meta = {
                    "n": created.get("n", 20),
                    "sec": created.get("sec", 1800),
                    "diff": created.get("diff", "mixed"),
                    "members": [self.app_state.username],
                }
                self.goto("waiting")

        elif cmd == "JOIN":
            if parts[0] == "OK" and len(parts) >= 9:
                # OK|JOINED|rid|name|owner|n|sec|diff|mems
                rid = int(parts[2])
                name = unescape_field(parts[3])
                owner = parts[4]
                self.app_state.room_id = rid
                self.app_state.room_name = name
                self.app_state.room_owner = owner
                self.app_state.room_meta = {
                    "n": parts[5],
                    "sec": parts[6],
                    "diff": parts[7],
                    "members": parts[8].split(",") if parts[8] else [],
                }
                self.goto("waiting")

        elif cmd == "ROOM_RESULT":
            if parts[0] == "OK":
                self.app_state.last_result = {
                    "raw": payload,
                    "rid": self.app_state.room_id,
                    "name": self.app_state.room_name,
                }
                self.goto("result")
