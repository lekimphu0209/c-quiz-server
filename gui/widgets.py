from PyQt5.QtCore import QTimer, pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
)


class StatusBadge(QFrame):
    """Visual pill badge representing room status."""

    def __init__(self, status="WAITING", parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(8, 4, 8, 4)
        self.layout.setSpacing(6)

        self.dot = QLabel("●")
        self.lbl_text = QLabel(status)
        self.lbl_text.setStyleSheet("font-weight: 700; font-size: 11px;")

        self.layout.addWidget(self.dot)
        self.layout.addWidget(self.lbl_text)
        self.set_status(status)

    def set_status(self, status: str):
        status = status.upper()
        self.lbl_text.setText(status)
        if status == "WAITING":
            self.setStyleSheet(
                "QFrame { background-color: rgba(16, 185, 129, 0.15); border: 1px solid #059669; border-radius: 12px; }"
            )
            self.dot.setStyleSheet("color: #10b981; font-size: 12px;")
            self.lbl_text.setStyleSheet("color: #34d399; font-weight: 700;")
        elif status == "RUNNING":
            self.setStyleSheet(
                "QFrame { background-color: rgba(245, 158, 11, 0.15); border: 1px solid #d97706; border-radius: 12px; }"
            )
            self.dot.setStyleSheet("color: #f59e0b; font-size: 12px;")
            self.lbl_text.setStyleSheet("color: #fbbf24; font-weight: 700;")
        else:  # FINISHED
            self.setStyleSheet(
                "QFrame { background-color: rgba(100, 116, 139, 0.15); border: 1px solid #475569; border-radius: 12px; }"
            )
            self.dot.setStyleSheet("color: #94a3b8; font-size: 12px;")
            self.lbl_text.setStyleSheet("color: #cbd5e1; font-weight: 700;")


class QuestionMatrix(QWidget):
    """Grid of buttons representing question status (1-indexed)."""

    question_clicked = pyqtSignal(int)

    def __init__(self, count=10, parent=None):
        super().__init__(parent)
        self.count = count
        self.current_idx = 1
        self.buttons = {}
        self.answered = [False] * (count + 1)

        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(4, 4, 4, 4)
        self.grid.setSpacing(6)
        self.init_buttons()

    def init_buttons(self):
        # Clear existing
        for btn in self.buttons.values():
            btn.deleteLater()
        self.buttons.clear()

        cols = 5
        for i in range(1, self.count + 1):
            btn = QPushButton(str(i))
            btn.setFixedSize(38, 38)
            btn.setCursor(Qt.PointingHandCursor)
            row = (i - 1) // cols
            col = (i - 1) % cols
            # Bind closure
            btn.clicked.connect(lambda checked, idx=i: self.on_btn_click(idx))
            self.grid.addWidget(btn, row, col)
            self.buttons[i] = btn
        self.update_styles()

    def set_count(self, count: int):
        self.count = count
        self.answered = [False] * (count + 1)
        self.current_idx = 1
        self.init_buttons()

    def set_mask(self, mask: str):
        """Update answered state from binary mask string '10110...'"""
        for i, ch in enumerate(mask, start=1):
            if i <= self.count:
                self.answered[i] = (ch == "1")
        self.update_styles()

    def set_answered(self, idx: int, status: bool = True):
        if 1 <= idx <= self.count:
            self.answered[idx] = status
            self.update_styles()

    def set_current(self, idx: int):
        if 1 <= idx <= self.count:
            self.current_idx = idx
            self.update_styles()

    def on_btn_click(self, idx: int):
        self.set_current(idx)
        self.question_clicked.emit(idx)

    def update_styles(self):
        for idx, btn in self.buttons.items():
            is_cur = (idx == self.current_idx)
            is_ans = self.answered[idx]

            bg = "#10b981" if is_ans else "#334155"
            border = "2px solid #818cf8" if is_cur else "1px solid #475569"
            color = "#ffffff" if (is_ans or is_cur) else "#94a3b8"
            font_weight = "800" if is_cur else "600"

            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {bg};
                    border: {border};
                    border-radius: 8px;
                    color: {color};
                    font-weight: {font_weight};
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    border: 2px solid #a5b4fc;
                }}
            """)


class CountdownLabel(QLabel):
    """Timer label displaying mm:ss with pulse effect when expiring."""

    time_up = pyqtSignal()
    tick = pyqtSignal(int)

    def __init__(self, seconds=600, parent=None):
        super().__init__(parent)
        self.remain = seconds
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.update_display()

    def start_countdown(self, seconds=None):
        if seconds is not None:
            self.remain = seconds
        self.update_display()
        self.timer.start(1000)

    def stop_countdown(self):
        self.timer.stop()

    def set_remain(self, sec: int):
        self.remain = sec
        self.update_display()

    def _on_tick(self):
        if self.remain > 0:
            self.remain -= 1
            self.update_display()
            self.tick.emit(self.remain)
            if self.remain == 0:
                self.timer.stop()
                self.time_up.emit()

    def update_display(self):
        mins = self.remain // 60
        secs = self.remain % 60
        self.setText(f"⏱  {mins:02d}:{secs:02d}")

        if self.remain <= 30:
            self.setStyleSheet("""
                QLabel {
                    color: #ef4444;
                    font-size: 18px;
                    font-weight: 800;
                    background-color: rgba(239, 68, 68, 0.15);
                    border: 1px solid #ef4444;
                    border-radius: 8px;
                    padding: 4px 10px;
                }
            """)
        else:
            self.setStyleSheet("""
                QLabel {
                    color: #818cf8;
                    font-size: 18px;
                    font-weight: 700;
                    background-color: rgba(99, 102, 241, 0.12);
                    border: 1px solid #4f46e5;
                    border-radius: 8px;
                    padding: 4px 10px;
                }
            """)
