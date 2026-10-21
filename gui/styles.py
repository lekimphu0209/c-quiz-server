# Modern sleek dark theme for PyQt5 Quiz Client
# Palette: Tailwind Slate / Indigo / Emerald / Amber / Rose

DARK_STYLE = """
/* Global defaults */
QWidget {
    background-color: #0f172a;
    color: #f8fafc;
    font-family: 'Segoe UI', 'Inter', -apple-system, sans-serif;
    font-size: 13px;
    selection-background-color: #6366f1;
    selection-color: #ffffff;
}

/* Window & StackedWidget */
QMainWindow, QStackedWidget {
    background-color: #0f172a;
}

/* Card Containers & Panels */
QFrame[card="true"], QGroupBox {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 16px;
}

QGroupBox {
    font-weight: bold;
    font-size: 14px;
    margin-top: 14px;
    padding-top: 24px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    color: #818cf8;
    background-color: transparent;
}

/* Headings and Labels */
QLabel {
    background-color: transparent;
    color: #f8fafc;
}

QLabel[heading="true"] {
    font-size: 22px;
    font-weight: 800;
    color: #f8fafc;
}

QLabel[subheading="true"] {
    font-size: 14px;
    color: #94a3b8;
}

QLabel[error="true"] {
    color: #f87171;
    font-size: 12px;
    font-weight: 600;
}

/* Buttons */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1);
    color: #ffffff;
    font-weight: 600;
    font-size: 13px;
    border: none;
    border-radius: 8px;
    padding: 8px 18px;
    min-height: 22px;
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #818cf8);
}

QPushButton:pressed {
    background: #3730a3;
}

QPushButton:disabled {
    background: #334155;
    color: #64748b;
}

/* Secondary / Ghost button */
QPushButton[secondary="true"] {
    background: #1e293b;
    color: #e2e8f0;
    border: 1px solid #475569;
}

QPushButton[secondary="true"]:hover {
    background: #334155;
    border-color: #64748b;
}

/* Danger Button */
QPushButton[danger="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:1 #ef4444);
}

QPushButton[danger="true"]:hover {
    background: #f87171;
}

/* Success Button */
QPushButton[success="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
}

QPushButton[success="true"]:hover {
    background: #34d399;
}

/* Inputs */
QLineEdit, QSpinBox, QComboBox {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 12px;
    color: #f8fafc;
    min-height: 20px;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #6366f1;
    background-color: #131d35;
}

/* ComboBox dropdown */
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 25px;
    border-left: 1px solid #334155;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}

QComboBox QAbstractItemView {
    background-color: #1e293b;
    border: 1px solid #475569;
    selection-background-color: #4f46e5;
    selection-color: #ffffff;
    color: #f8fafc;
    padding: 4px;
}

/* Tables */
QTableWidget {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    gridline-color: #2a374d;
    selection-background-color: #3730a3;
    selection-color: #ffffff;
}

QTableWidget::item {
    padding: 10px;
    border-bottom: 1px solid #2a374d;
}

QTableWidget::item:selected {
    background-color: #3730a3;
}

QHeaderView::section {
    background-color: #0f172a;
    color: #94a3b8;
    padding: 10px;
    font-weight: 700;
    font-size: 12px;
    border: none;
    border-bottom: 2px solid #475569;
}

/* Radio buttons */
QRadioButton {
    spacing: 12px;
    color: #f8fafc;
    font-size: 14px;
    padding: 8px;
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
}

QRadioButton:hover {
    border-color: #6366f1;
    background-color: #243048;
}

QRadioButton:checked {
    border-color: #818cf8;
    background-color: #262c54;
    font-weight: 600;
}

QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border-radius: 9px;
    border: 2px solid #64748b;
    background: transparent;
}

QRadioButton::indicator:checked {
    border: 5px solid #6366f1;
    background: #ffffff;
}

/* Lists */
QListWidget {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 6px;
}

QListWidget::item {
    padding: 8px;
    border-radius: 6px;
    color: #f8fafc;
}

QListWidget::item:hover {
    background-color: #334155;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #334155;
    background: #1e293b;
    border-radius: 10px;
    padding: 8px;
}

QTabBar::tab {
    background: #0f172a;
    color: #94a3b8;
    padding: 10px 24px;
    font-weight: 600;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 4px;
}

QTabBar::tab:selected {
    background: #1e293b;
    color: #818cf8;
    border-bottom: 2px solid #818cf8;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #0f172a;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #475569;
    min-height: 25px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #64748b;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Dialogs */
QDialog {
    background-color: #0f172a;
}
"""
