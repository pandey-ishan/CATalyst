"""Warm paper, ink and quiet sage: a local study notebook."""
STYLE = '''
QWidget { background: #faf7f0; color: #26394c; font-family: "Segoe UI"; font-size: 14px; }
QWidget#workspace { background: #faf7f0; border: 1px solid #dae3ed; border-radius: 26px; }
QLabel { background: transparent; border: none; }
QLabel#title { font-size: 26px; font-weight: 600; }
QLabel#heroTitle { font-size: 34px; font-weight: 500; }
QLabel#eyebrow { font-size: 10px; color: #62809b; letter-spacing: 1px; }
QLabel#sectionTitle { font-size: 18px; font-weight: 600; }
QLabel#subtitle, QLabel#cardTitle { color: #647b90; }
QLabel#metric { font-size: 34px; font-weight: 500; color: #254b72; }
QLabel#pill { border: 1px solid #d2e0f1; border-radius: 18px; padding: 10px 16px; color: #4a6c90; background: #edf4fd; }
QLabel#warning { background: #f0e5dd; color: #775347; border-radius: 14px; padding: 12px; font-size: 12px; }
QLabel#emptyHint { color: #747d70; padding: 16px 0; }
QFrame#metricCard, QFrame#panel { background: #fffdf7; border: 1px solid #deddd3; border-radius: 22px; }
QFrame#goldCard { background: #e7f1ff; border: 1px solid #c9dcf3; border-radius: 22px; }
QFrame#focusCard { background: #fff0e3; border: 1px solid #f1d5be; border-radius: 22px; }
QGroupBox { border: 1px solid #d2d7cb; border-radius: 18px; margin-top: 16px; padding: 15px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; color: #53604e; }
QPushButton { background: #faf9f2; border: 1px solid #cbd1c4; border-radius: 18px; padding: 10px 16px; color: #365b7d; }
QPushButton:hover { background: #e8f1fd; border-color: #91b4d6; }
QPushButton:pressed { background: #d9e9fa; }
QPushButton:disabled { color: #91978b; background: #eeeee6; border-color: #dedfd6; }
QPushButton#primary { background: #c56624; color: #fffdf7; border: none; font-weight: 600; }
QPushButton#primary:hover { background: #ac551d; }
QPushButton#topicRow { text-align: left; padding: 11px 14px; background: #edf5ff; border: 1px solid #d1e2f6; border-radius: 16px; font-size: 13px; }
QPushButton#topicRow:hover { background: #deecff; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateEdit { background: #fffdf8; border: 1px solid #cdd3c4; border-radius: 14px; padding: 8px; selection-background-color: #dce6d4; selection-color: #243020; }
QPlainTextEdit { font-size: 17px; }
QTextBrowser#questionReader { background: #fffdf8; border: 1px solid #d4d7cb; border-radius: 20px; padding: 22px; selection-background-color: #dce6d4; }
QListWidget#entryList { background: transparent; border: none; outline: none; }
QTabWidget::pane { border: none; padding-top: 10px; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 4px 0; }
QScrollBar::handle:vertical { background: #b5cce5; border-radius: 4px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QProgressBar { background: #dce9f8; border: none; border-radius: 3px; }
QProgressBar::chunk { background: #e58a42; border-radius: 3px; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #9ba991; border-radius: 9px; background: #fffdf8; }
QCheckBox::indicator:checked { background: #4d87c5; border: 4px solid #d6e6f9; }
QWidget#recordingNotch { background: #f5f5ec; border: 1px solid #b9c6ad; border-radius: 22px; }
QCalendarWidget { background: #fffdf7; border-radius: 18px; }
QCalendarWidget QWidget { background: #fffdf7; alternate-background-color: #f0f2e8; }
QCalendarWidget QToolButton { color: #406a92; background: #edf4fe; border: none; border-radius: 12px; padding: 6px; }
QCalendarWidget QAbstractItemView { background: #fffdf7; selection-background-color: #ffe4cd; selection-color: #7e431c; border: none; border-radius: 14px; }
QToolTip { background: #fffdf7; color: #35452e; border: 1px solid #becbb3; border-radius: 8px; padding: 6px; }
'''

STYLE += "QWidget#notebookPage { background: transparent; border: none; border-radius: 22px; }"

STYLE += """
QTableWidget#readableTable { background: #fffdf8; border: 1px solid #d9e4f1; border-radius: 18px; padding: 7px; outline: none; }
QHeaderView { background: transparent; }
QHeaderView::section { background: #eaf2fd; color: #486782; border: none; border-radius: 10px; padding: 12px 8px; font-weight: 600; }
QTableWidget::item { border: none; }
QScrollBar:horizontal { background: transparent; height: 9px; }
QScrollBar::handle:horizontal { background: #b5cce5; border-radius: 4px; min-width: 25px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
"""

STYLE += """
QWidget#rowActions { background: transparent; }
QToolButton { background: #edf4ff; border: 1px solid #d4e2f3; border-radius: 12px; padding: 4px; }
QToolButton:hover { background: #ffe6ce; }
QHeaderView { background: #eaf2fd; border-radius: 14px; }
QHeaderView::section { background: transparent; border: none; border-radius: 0; }
QWidget#recordingNotch { border-top-left-radius: 0; border-top-right-radius: 0; border-bottom-left-radius: 24px; border-bottom-right-radius: 24px; }
"""

STYLE += "QListWidget#navigation { background: #e9f2ff; border: 1px solid #cddff5; border-radius: 22px; padding: 8px 0; outline: none; }"
