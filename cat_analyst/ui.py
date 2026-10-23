from __future__ import annotations
import json
import html
from pathlib import Path
from PySide6.QtCore import Qt, QRect, QPoint, Signal, QTimer, QDate, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QDoubleValidator, QRegion, QPainterPath
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QFormLayout, QLineEdit, QPlainTextEdit, QComboBox, QCheckBox, QSpinBox, QDialogButtonBox,
    QMessageBox, QScrollArea, QAbstractItemView, QGroupBox, QDateEdit, QListWidget, QListWidgetItem, QStyle)
from PySide6.QtCharts import QChart, QChartView, QLineSeries
from .core import Question, Session, Store, TOPICS, SECTIONS, analytics, data_directory, today_local
from .capture import CaptureWorker
from .display import selection_region

from .theme import STYLE
from .reader import QuestionReader
from .dashboard import Dashboard
from .calendar_panel import MockCalendar
from .icons import line_icon
from .tables import ReadableTable
from .navigation import NavigationDelegate


def button(text, callback, primary=False):
    widget = QPushButton(text)
    widget.clicked.connect(callback)
    if primary:
        widget.setObjectName('primary')
    return widget


def label(text, role=None):
    widget = QLabel(text)
    if role:
        widget.setObjectName(role)
    return widget


def table(headers):
    return ReadableTable(headers)


def fill_table(widget, rows):
    widget.set_rows(rows)


def clock_text(seconds):
    if seconds is None:
        return '—'
    seconds = round(seconds)
    return f'{seconds // 60}:{seconds % 60:02d}'


class QuestionEditor(QDialog):
    def __init__(self, question: Question, parent=None, images=None):
        super().__init__(parent)
        self.question = question
        self.original = {}
        self.fields = {}
        self.setWindowTitle(f'Question {question.number} · Review and edit')
        self.resize(820, 800)
        outer = QVBoxLayout(self)
        status = ', '.join(question.missing()) or 'All required fields captured'
        message = label('Check: ' + status + ('\n' + '\n'.join(question.warnings) if question.warnings else ''))
        message.setWordWrap(True)
        outer.addWidget(message)
        hint = label('Write exponents as x^{2}, x^(n+1), or (0.125)^{-80}. View question renders them as superscripts.', 'subtitle')
        hint.setWordWrap(True)
        outer.addWidget(hint)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QFormLayout(inner)
        for key, title in [('text', 'Question and options'), ('solution', 'Text solution')]:
            field = QPlainTextEdit(getattr(question, key))
            field.setMinimumHeight(145)
            self.fields[key] = field
            self.original[key] = getattr(question, key)
            form.addRow(title, field)
        for key, title in [('correct_answer', 'Correct answer'), ('selected_answer', 'Your answer')]:
            field = QLineEdit(getattr(question, key))
            self.fields[key] = field
            self.original[key] = getattr(question, key)
            form.addRow(title, field)
        for key, title, options in [('difficulty', 'Difficulty', ['Unknown', 'Easy', 'Medium', 'Hard']),
                                    ('attempted', 'Attempt', ['Unknown', 'Answered', 'Unattempted']),
                                    ('correctness', 'Result', ['Unknown', 'Correct', 'Incorrect']),
                                    ('topic', 'Topic', TOPICS)]:
            field = QComboBox()
            field.addItems(options)
            field.setCurrentText(getattr(question, key))
            self.fields[key] = field
            self.original[key] = getattr(question, key)
            form.addRow(title, field)
        time_field = QLineEdit('' if question.seconds is None else clock_text(question.seconds))
        time_field.setPlaceholderText('m:ss, or leave blank if unknown')
        self.fields['seconds'] = time_field
        self.original['seconds'] = question.seconds
        form.addRow('Time spent in mock', time_field)
        self.bookmark = QCheckBox('Bookmark this question')
        self.bookmark.setChecked(question.bookmark)
        form.addRow(self.bookmark)
        raw = QPlainTextEdit(question.raw_text)
        raw.setReadOnly(True)
        raw.setMaximumHeight(120)
        form.addRow('Raw captured text', raw)
        for data in images or []:
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            view = QLabel()
            view.setPixmap(pixmap.scaledToWidth(680, Qt.TransformationMode.SmoothTransformation))
            form.addRow('Saved screenshot', view)
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(self.save)
        controls.rejected.connect(self.reject)
        outer.addWidget(controls)

    def save(self):
        values = {}
        for key, field in self.fields.items():
            if isinstance(field, QPlainTextEdit):
                values[key] = field.toPlainText().strip()
            elif isinstance(field, QComboBox):
                values[key] = field.currentText()
            else:
                values[key] = field.text().strip()
        text = values['seconds']
        try:
            if text:
                minute, second = text.split(':')
                if int(minute) < 0 or not 0 <= int(second) <= 59:
                    raise ValueError()
                values['seconds'] = int(minute) * 60 + int(second)
            else:
                values['seconds'] = None
        except ValueError:
            QMessageBox.warning(self, 'Check time', 'Enter time as m:ss, for example 3:10.')
            return
        for key, value in values.items():
            if self.original[key] != value:
                setattr(self.question, key, value)
                if key not in self.question.locked:
                    self.question.locked.append(key)
        self.question.bookmark = self.bookmark.isChecked()
        self.accept()


class ReviewWindow(QDialog):
    changed = Signal()

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle('Live question review')
        self.viewer = None
        self.resize(1150, 650)
        layout = QVBoxLayout(self)
        self.summary = label('')
        layout.addWidget(self.summary)
        layout.addWidget(label('View a question without ending the session. Return to test provider to continue capture; edits are protected from OCR.', 'subtitle'))
        self.table = table(['QA #', 'Topic', 'Difficulty', 'Attempt', 'Result', 'Time', 'Needs review'])
        layout.addWidget(self.table)
        self.table.cellDoubleClicked.connect(self.view)
        self.table.set_actions([('View question','review',self.view),('Edit question','edit',self.edit),('Delete question','delete',self.delete)])
        controls = QHBoxLayout()
        self.view_button = button('View question', lambda: self.view(self.table.currentRow(), 0), True)
        self.view_button.hide()
        controls.addWidget(button('Add missing question', self.add))
        controls.addStretch()
        layout.addLayout(controls)
        self.refresh()

    def refresh(self):
        current = self.table.currentRow()
        previous_number = self.numbers[current] if hasattr(self, 'numbers') and 0 <= current < len(self.numbers) else None
        self.numbers = sorted(self.session.questions)
        questions = [self.session.questions[n] for n in self.numbers]
        self.summary.setText(f'{len(questions)} / {self.session.expected} QA questions captured · ' +
                             f'{sum(bool(q.missing()) for q in questions)} incomplete')
        fill_table(self.table, [(q.number, q.topic, q.difficulty, q.attempted, q.correctness,
                               clock_text(q.seconds), ', '.join(q.missing()) or ('Check warnings' if q.warnings else 'Ready'))
                              for q in questions])
        self.view_button.setEnabled(bool(self.numbers))
        if self.numbers:
            self.table.selectRow(self.numbers.index(previous_number) if previous_number in self.numbers else 0)
        if self.viewer and self.viewer.isVisible():
            self.viewer.refresh(preserve_scroll=True)

    def view(self, row, column=0):
        if not self.numbers:
            return
        if self.viewer:
            self.viewer.close()
        self.viewer = QuestionReader([('Current recording', self.session.questions[n]) for n in self.numbers],
                                     max(0, row), self)
        self.viewer.changed.connect(lambda q: self.changed.emit())
        self.viewer.changed.connect(lambda q: self.refresh())
        self.viewer.show()

    def edit(self, row, column=0):
        if row < 0 or row >= len(self.numbers):
            return
        if QuestionEditor(self.session.questions[self.numbers[row]], self).exec():
            self.changed.emit()
            self.refresh()

    def delete(self,row):
        if not 0<=row<len(self.numbers):return
        number=self.numbers[row]
        if QMessageBox.question(self,'Delete draft question?',f'Delete question {number} from this draft? Revisiting it in test provider may capture it again.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        if self.viewer:self.viewer.close()
        del self.session.questions[number]
        self.changed.emit();self.refresh()

    def add(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Add QA question')
        form = QFormLayout(dialog)
        number = QSpinBox()
        number.setRange(1, 100)
        number.setValue(next((x for x in range(1, 101) if x not in self.session.questions), 1))
        form.addRow('Question number', number)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(dialog.accept)
        controls.rejected.connect(dialog.reject)
        form.addRow(controls)
        if dialog.exec():
            q = self.session.questions.setdefault(number.value(), Question(number.value()))
            QuestionEditor(q, self).exec()
            self.changed.emit()
            self.refresh()


class SaveDialog(QDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.metrics = {}
        self.setWindowTitle('Save mock paper')
        layout = QVBoxLayout(self)
        self.info = label('')
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText('e.g. test provider SIMCAT 12')
        form.addRow('Paper name', self.name)
        self.test_date = QDateEdit(QDate.fromString(session.test_date, 'yyyy-MM-dd'))
        self.test_date.setCalendarPopup(True)
        self.test_date.setMaximumDate(QDate.fromString(today_local().isoformat(), 'yyyy-MM-dd'))
        self.test_date.setDisplayFormat('dd MMM yyyy')
        form.addRow('Test date', self.test_date)
        self.expected = QSpinBox()
        self.expected.setRange(1, 100)
        self.expected.setValue(session.expected)
        self.expected.valueChanged.connect(self.update_summary)
        form.addRow('Expected QA questions', self.expected)
        self.inputs = {}
        for section in SECTIONS:
            row = QHBoxLayout()
            score, percentile = QLineEdit(), QLineEdit()
            score.setPlaceholderText('Score')
            percentile.setPlaceholderText('Percentile (0–100)')
            score.setValidator(QDoubleValidator(-300, 300, 3, self))
            percentile.setValidator(QDoubleValidator(0, 100, 4, self))
            row.addWidget(score)
            row.addWidget(percentile)
            self.inputs[section] = (score, percentile)
            form.addRow(section, row)
        layout.addLayout(form)
        self.ack = QCheckBox('I reviewed the incomplete fields / coverage and want to save this draft as a paper')
        layout.addWidget(self.ack)
        layout.addWidget(label('Recording is deleted only after the paper saves successfully.', 'subtitle'))
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(self.validate)
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)
        self.update_summary()

    def update_summary(self):
        missing = sorted(set(range(1, self.expected.value() + 1)) - self.session.questions.keys())
        outside = [n for n in self.session.questions if n > self.expected.value()]
        incomplete = sum(bool(q.missing() or q.warnings) for q in self.session.questions.values())
        self.needs_ack = bool(missing or outside or incomplete)
        self.info.setText(f'{len(self.session.questions)} questions · {incomplete} need review.\n' +
                          ('Missing question numbers: ' + ', '.join(map(str, missing)) if missing else 'All question numbers present.') +
                          ('\nOut-of-range numbers: ' + ', '.join(map(str, outside)) if outside else ''))
        self.ack.setVisible(self.needs_ack)

    def validate(self):
        try:
            if not self.name.text().strip():
                raise ValueError('Enter a paper name.')
            if not self.session.questions and not getattr(self, "editing_existing", False):
                raise ValueError('No questions captured. Add or capture questions before saving.')
            for section, (score, percentile) in self.inputs.items():
                if not score.hasAcceptableInput() or not percentile.hasAcceptableInput():
                    raise ValueError(f'Enter a valid score and percentile for {section}.')
                self.metrics[section] = {'score': float(score.text()), 'percentile': float(percentile.text())}
            if self.needs_ack and not self.ack.isChecked():
                raise ValueError('Review the coverage warning and select the acknowledgment to save incomplete data.')
        except ValueError as error:
            QMessageBox.warning(self, 'Check paper details', str(error))
            return
        self.session.test_date = self.test_date.date().toString("yyyy-MM-dd")
        self.session.expected = self.expected.value()
        self.accept()


class RegionSelector(QWidget):
    selected = Signal(dict)
    cancelled = Signal()

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.screen = QApplication.primaryScreen()
        self.setGeometry(self.screen.geometry())
        self.background = self.screen.grabWindow(0)
        self.origin = QPoint()
        self.selection = QRect()
        self.completed = False
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.background)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 105))
        painter.setPen(QPen(QColor('#6ee7c7'), 3))
        painter.drawRect(self.selection)
        painter.setPen(QColor('white'))
        painter.drawText(30, 40, 'Drag around the test provider question and review panel. Include question number. Escape cancels.')

    def mousePressEvent(self, event):
        self.origin = event.position().toPoint()
        self.selection = QRect(self.origin, self.origin)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.selection = QRect(self.origin, event.position().toPoint()).normalized().intersected(self.rect())
            self.update()

    def mouseReleaseEvent(self, event):
        if self.selection.width() < 250 or self.selection.height() < 200:
            return
        import mss
        r = self.selection
        try:
            with mss.mss() as capture:
                region = selection_region(capture.monitors, self.screen.geometry().width(),
                                          self.screen.geometry().height(),
                                          r.left(), r.top(), r.width(), r.height())
        except ValueError as error:
            QMessageBox.warning(self, 'Cannot select display', str(error))
            return
        self.completed = True
        self.close()
        self.selected.emit(region)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def closeEvent(self, event):
        if not self.completed:
            self.cancelled.emit()
        event.accept()


class FloatingToolbar(QWidget):
    def __init__(self, owner):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.owner = owner
        self.compact = False
        self.setObjectName('recordingNotch')
        self.setWindowTitle('CATalyst recording controls')
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.state = label('RECORDING', 'subtitle')
        controls.addWidget(self.state)
        self.pause_button = button('Pause', owner.toggle_pause)
        controls.addWidget(self.pause_button)
        self.review_button = button('Review', owner.show_review)
        self.review_button.setIcon(line_icon('review'))
        controls.addWidget(self.review_button)
        self.stop_button = button('Stop & save', owner.stop_capture, True)
        controls.addWidget(self.stop_button)
        self.expand_button = button('Collapse', self.toggle_size)
        controls.addWidget(self.expand_button)
        layout.addLayout(controls)
        self.status = label('Starting local capture...')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.collapse_timer = QTimer(self)
        self.collapse_timer.setSingleShot(True)
        self.collapse_timer.timeout.connect(lambda: self.set_compact(True))
        self.set_compact(False)

    def set_compact(self, compact):
        self.compact = compact
        self.state.setVisible(not compact)
        self.status.setVisible(not compact)
        self.stop_button.setVisible(not compact)
        self.expand_button.setText('More' if compact else 'Collapse')
        self.set_paused(self.owner.paused)
        self.setFixedSize(310 if compact else 690, 58 if compact else 118)
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.center().x() - self.width() // 2, screen.top())
        if compact:
            self.collapse_timer.stop()
        else:
            self.collapse_timer.start(4000)

    def enterEvent(self,event):
        self.set_compact(False)
        self.collapse_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self,event):
        self.collapse_timer.start(4000)
        super().leaveEvent(event)

    def resizeEvent(self,event):
        path=QPainterPath();path.addRoundedRect(0,-24,self.width(),self.height()+24,24,24)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(event)

    def toggle_size(self):
        self.set_compact(not self.compact)

    def set_paused(self, paused):
        self.state.setText('PAUSED' if paused else 'RECORDING')
        self.pause_button.setText('' if self.compact else ('Resume' if paused else 'Pause'))
        self.pause_button.setIcon(line_icon('play' if paused else 'pause'))
        self.pause_button.setToolTip('Resume recording' if paused else 'Pause recording')
        self.pause_button.setAccessibleName(self.pause_button.toolTip())

    def closeEvent(self, event):
        if self.owner.worker and self.owner.worker.isRunning():
            self.owner.stop_capture()
            event.ignore()
        else:
            self.collapse_timer.stop()
            event.accept()


class MainWindow(QMainWindow):
    def __init__(self, root: Path | None = None):
        super().__init__()
        self.store = Store(root or data_directory())
        self.worker = None
        self.session = None
        self.review = None
        self.toolbar = None
        self.paused = False
        self.setWindowTitle('CATalyst')
        available = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1440, int(available.width() * .94)), min(940, int(available.height() * .9)))
        self.move(available.center() - self.rect().center())
        central = QWidget()
        central.setObjectName("workspace")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        heading = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(label('CATalyst', 'title'))
        heading.addLayout(titles)
        heading.addStretch()
        self.recover_button = button('Recover draft', self.recover)
        self.recover_button.setIcon(line_icon('recover'))
        heading.addWidget(self.recover_button)
        self.start_button = button('New recording', self.new_capture, True)
        self.start_button.setIcon(line_icon('plus', '#ffffff'))
        heading.addWidget(self.start_button)
        layout.addLayout(heading)
        self.tabs = QTabWidget()
        self.tabs.tabBar().hide()
        body = QHBoxLayout()
        self.navigation = QListWidget()
        self.navigation.setObjectName('navigation')
        self.navigation.setFixedWidth(66)
        self.navigation.setItemDelegate(NavigationDelegate(self.navigation))
        self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.navigation.setIconSize(QSize(20,20))
        for title, icon in [('Overview', 'overview'), ('Papers', 'papers'), ('Bookmarks', 'bookmark')]:
            item = QListWidgetItem(line_icon(icon), '')
            item.setToolTip(title)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, title)
            item.setSizeHint(QSize(64, 52))
            self.navigation.addItem(item)
        body.addWidget(self.navigation)
        body.addWidget(self.tabs, 1)
        layout.addLayout(body)
        self.navigation.currentRowChanged.connect(self.tabs.setCurrentIndex)
        self.tabs.currentChanged.connect(self.navigation.setCurrentRow)
        self.build_dashboard()
        self.build_library()
        self.build_bookmarks()
        self.navigation.setCurrentRow(0)
        self.calendar_timer = QTimer(self)
        self.calendar_timer.timeout.connect(lambda: self.calendar.update_papers(self.store.papers()))
        self.calendar_timer.start(60000)
        self.statusBar().showMessage(f'Local storage: {self.store.root}')
        self.refresh()

    def build_dashboard(self):
        self.dashboard = Dashboard(self)
        self.cards = self.dashboard.cards
        self.dashboard.topic_requested.connect(self.view_topic)
        self.dashboard.review_requested.connect(lambda: self.tabs.setCurrentIndex(2))
        page = QWidget()
        page.setObjectName("notebookPage")
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.dashboard, 1)
        self.calendar = MockCalendar()
        self.calendar.paper_requested.connect(self.open_paper)
        self.calendar_scroll = QScrollArea()
        self.calendar_scroll.setWidgetResizable(True)
        self.calendar_scroll.setFixedWidth(294)
        self.calendar_scroll.setWidget(self.calendar)
        layout.addWidget(self.calendar_scroll)
        self.calendar_scroll.setMaximumHeight(650)
        self.tabs.addTab(page, 'Overview')

    def build_library(self):
        page = QWidget()
        page.setObjectName("notebookPage")
        layout = QVBoxLayout(page)
        self.paper_table = table(['Paper', 'Date', 'Overall', 'VARC', 'DILR', 'QA', 'Percentile'])
        self.paper_table.itemSelectionChanged.connect(self.select_paper)
        self.paper_table.set_actions([('View test','review',lambda r:self.open_paper(self.paper_rows[r]['id'])),('Edit test','edit',self.edit_paper),('Delete test','delete',self.delete_paper_row)])
        layout.addWidget(label('Your mock notebook', 'title'))
        layout.addWidget(self.paper_table, 2)
        self.paper_details = label('Select a paper to review its QA questions.')
        self.paper_details.setWordWrap(True)
        layout.addWidget(self.paper_details)
        self.question_table = table(['QA #', 'Topic', 'Difficulty', 'Attempt', 'Result', 'Time', 'Bookmark'])
        self.question_table.cellDoubleClicked.connect(lambda row, col: self.view_saved(row, False))
        self.question_table.set_actions([('View question','review',lambda r:self.view_saved(r,False)),('Edit question','edit',lambda r:self.edit_saved(r,False)),('Delete question','delete',self.delete_question_row)])
        layout.addWidget(self.question_table, 3)
        self.tabs.addTab(page, 'Papers')

    def build_bookmarks(self):
        page = QWidget()
        page.setObjectName("notebookPage")
        layout = QVBoxLayout(page)
        layout.addWidget(label('Questions to return to', 'title'))
        self.bookmark_table = table(['Paper', 'QA #', 'Topic', 'Difficulty'])
        self.bookmark_table.cellDoubleClicked.connect(lambda row, col: self.view_saved(row, True))
        layout.addWidget(self.bookmark_table)
        self.bookmark_table.set_actions([('View question','review',lambda r:self.view_saved(r,True)),('Edit question','edit',lambda r:self.edit_saved(r,True)),('Delete question','delete',lambda r:self.delete_question_row(r,True))])
        self.tabs.addTab(page, 'Bookmarks')

    def refresh(self):
        papers = self.store.papers()
        self.paper_rows = papers
        questions = [row[2] for row in self.store.questions()]
        self.dashboard.update_data(papers, questions)
        self.calendar.update_papers(papers)
        self.paper_table.blockSignals(True)
        fill_table(self.paper_table, [(p['name'], p['test_date'],
                    *[f"{json.loads(p['metrics'])[s]['score']:g}" for s in SECTIONS],
                    f"{json.loads(p['metrics'])['Overall']['percentile']:.2f}") for p in papers])
        self.paper_table.blockSignals(False)
        self.bookmark_rows = self.store.questions(bookmarks=True)
        fill_table(self.bookmark_table, [(name, q.number, q.topic, q.difficulty)
                                        for _, name, q in self.bookmark_rows])
        for row,(_,_,question) in enumerate(self.bookmark_rows):
            tooltip='<div style="max-width:520px;white-space:pre-wrap">'+html.escape(question.text or 'Question text not captured')+'</div>'
            for col in range(self.bookmark_table.action_column):
                self.bookmark_table.item(row,col).setToolTip(tooltip)
        self.saved_rows = []
        self.question_table.setRowCount(0)
        self.recover_button.setEnabled(bool(list((self.store.root / 'sessions').glob('*/draft.json'))) or self.session is not None)

    def open_paper(self, paper_id):
        self.tabs.setCurrentIndex(1)
        for i, paper in enumerate(self.paper_rows):
            if paper['id'] == paper_id:
                self.paper_table.selectRow(i)
                self.select_paper()
                break

    def delete_paper_row(self,row):
        self.paper_table.selectRow(row)
        self.delete_selected_paper()

    def delete_question_row(self,row,bookmarked=False):
        if bookmarked:
            pid,_,q=self.bookmark_rows[row]
            number=q.number
            self.open_paper(pid)
            row=next(i for i,entry in enumerate(self.saved_rows) if entry[2].number==number)
        self.question_table.selectRow(row)
        self.delete_selected_question()

    def edit_paper(self,row):
        paper=self.paper_rows[row]
        session=Session(id=paper['id'],created=paper['created'],test_date=paper['test_date'],expected=paper['expected'],questions={q.number:q for _,_,q in self.store.questions(paper['id'])})
        dialog=SaveDialog(session,self)
        dialog.setWindowTitle('Edit test details')
        dialog.editing_existing=True
        dialog.name.setText(paper['name'])
        metrics=json.loads(paper['metrics'])
        for section,(score,percentile) in dialog.inputs.items():
            score.setText(str(metrics[section]['score']));percentile.setText(str(metrics[section]['percentile']))
        if dialog.exec():
            with self.store.db:
                self.store.db.execute('UPDATE papers SET name=?,test_date=?,expected=?,metrics=? WHERE id=?',(dialog.name.text().strip(),session.test_date,session.expected,json.dumps(dialog.metrics),paper['id']))
            self.refresh();self.open_paper(paper['id'])

    def delete_selected_paper(self):
        row = self.paper_table.currentRow()
        if not 0 <= row < len(self.paper_rows):
            return
        paper = self.paper_rows[row]
        if QMessageBox.question(self, 'Delete test?', f"Delete {paper['name']} and all its questions and screenshots? This cannot be undone.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        if getattr(self, 'saved_reader', None):
            self.saved_reader.close()
        self.store.delete_paper(paper['id'])
        self.refresh()
        self.paper_details.setText('Test deleted. Select a paper to review.')

    def delete_selected_question(self):
        row = self.question_table.currentRow()
        if not 0 <= row < len(self.saved_rows):
            return
        paper_id, name, q = self.saved_rows[row]
        if QMessageBox.question(self, 'Delete question?', f'Delete question {q.number} from {name}, including saved screenshots? This cannot be undone.', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        if getattr(self, 'saved_reader', None):
            self.saved_reader.close()
        self.store.delete_question(paper_id, q.number)
        self.refresh()
        self.open_paper(paper_id)

    def select_paper(self):
        row = self.paper_table.currentRow()
        if row < 0 or row >= len(self.paper_rows):
            return
        paper = self.paper_rows[row]
        self.saved_rows = self.store.questions(paper['id'])
        metrics = json.loads(paper['metrics'])
        self.paper_details.setText(f"{paper['name']} · QA coverage {len(self.saved_rows)}/{paper['expected']}\nPercentiles: " +
                                  ' · '.join(f"{s} {metrics[s]['percentile']:.2f}" for s in SECTIONS))
        fill_table(self.question_table, [(q.number, q.topic, q.difficulty, q.attempted, q.correctness,
                                        clock_text(q.seconds), 'Saved' if q.bookmark else '') for _, _, q in self.saved_rows])

    def view_saved(self, row, bookmarked=False):
        source = self.bookmark_rows if bookmarked else self.saved_rows
        if source:
            self.open_saved_reader(source, max(0, row))

    def view_topic(self, topic):
        source = [entry for entry in self.store.questions() if entry[2].topic == topic]
        if source:
            self.open_saved_reader(source, 0)

    def open_saved_reader(self, source, index):
        ids = {id(q): paper_id for paper_id, _, q in source}
        def changed(q):
            self.store.update_question(ids[id(q)], q)
            self.refresh()
            row = next((i for i,p in enumerate(self.paper_rows) if p['id']==ids[id(q)]), -1)
            if row >= 0:
                self.paper_table.selectRow(row)
        if getattr(self, 'saved_reader', None):
            self.saved_reader.close()
        self.saved_reader = QuestionReader([(name, q) for _, name, q in source], index, self,
                                          lambda q: self.store.images(ids[id(q)], q.number))
        self.saved_reader.changed.connect(changed)
        self.saved_reader.show()

    def edit_saved(self, row, bookmarked):
        source = self.bookmark_rows if bookmarked else self.saved_rows
        if row < 0 or row >= len(source):
            return
        paper_id, name, q = source[row]
        if QuestionEditor(q, self, self.store.images(paper_id, q.number)).exec():
            self.store.update_question(paper_id, q)
            self.refresh()
            index = next((i for i, p in enumerate(self.paper_rows) if p['id'] == paper_id), -1)
            if index >= 0:
                self.paper_table.selectRow(index)

    def new_capture(self):
        if self.session is not None:
            self.show_review()
            QMessageBox.information(self, 'Current draft', 'Save the current draft before starting another recording. Use Recover / review draft to save or resume it.')
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('Start a review recording')
        layout = QVBoxLayout(dialog)
        instructions = label('Open test provider QA review on your primary display.\nSelect the question and review panel, including the question number.\nBrowse Statistics and Text Solution yourself; capture is automatic.\nKeep the floating toolbar outside the selected area. Pause whenever needed.')
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        screenshots = QCheckBox('Also save screenshots with questions (off by default)')
        layout.addWidget(screenshots)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(dialog.accept)
        controls.rejected.connect(dialog.reject)
        layout.addWidget(controls)
        if dialog.exec():
            self.session = Session(keep_screenshots=screenshots.isChecked())
            self.choose_region()

    def choose_region(self):
        self.hide()
        if self.review:
            self.review.hide()
        QTimer.singleShot(300, self.select_region)

    def select_region(self):
        self.selector = RegionSelector()
        self.selector.selected.connect(self.begin_capture)
        self.selector.cancelled.connect(self.cancel_region)
        self.selector.show()

    def cancel_region(self):
        if self.session and not self.session.questions:
            self.session = None
        self.show()

    def persist(self):
        try:
            if self.session:
                self.session.dump(self.store.session_dir(self.session))
            return True
        except OSError as error:
            if self.worker and self.worker.isRunning():
                self.paused = True
                self.worker.pause(True)
                self.toolbar.state.setText('PAUSED')
                self.toolbar.set_paused(True)
                self.toolbar.status.setText('Paused because the draft could not be written.')
            QMessageBox.critical(self, 'Draft could not be saved',
                                 f'{error}\nCollected questions remain in memory. Free disk space before continuing.')
            return False

    def begin_capture(self, region):
        self.session.region = region
        if not self.persist():
            self.show()
            return
        self.paused = False
        self.worker = CaptureWorker(region, self.store.session_dir(self.session), self.session.keep_screenshots)
        self.worker.observation.connect(self.on_observation)
        self.worker.status.connect(self.capture_status)
        self.worker.failure.connect(self.capture_error)
        self.worker.finished.connect(self.capture_finished)
        self.toolbar = FloatingToolbar(self)
        self.toolbar.show()
        self.start_button.setEnabled(False)
        self.worker.start()

    def capture_status(self, message):
        if self.toolbar and not self.paused:
            self.toolbar.status.setText(message)

    def on_observation(self, observation):
        generation, question = observation
        if self.session and not self.paused and self.worker and generation == self.worker.state()[2]:
            self.session.merge(question)
            if question.expected:
                totals = {q.expected for q in self.session.questions.values() if q.expected}
                if len(totals) == 1:
                    self.session.expected = question.expected
                else:
                    warning = 'Conflicting question totals; verify expected QA count before saving'
                    if warning not in self.session.questions[question.number].warnings:
                        self.session.questions[question.number].warnings.append(warning)
            self.persist()
            if self.review:
                self.review.refresh()

    def toggle_pause(self):
        if self.worker:
            self.paused = not self.paused
            self.worker.pause(self.paused)
            self.toolbar.state.setText('PAUSED' if self.paused else 'RECORDING')
            self.toolbar.set_paused(self.paused)
            self.toolbar.status.setText('Paused. No new screen content is being recorded.' if self.paused else 'Resumed. Browse test provider to capture.')
            self.persist()

    def show_review(self):
        if not self.session:
            return
        if self.review is None or self.review.session is not self.session:
            self.review = ReviewWindow(self.session, self)
            self.review.changed.connect(self.persist)
        self.review.refresh()
        self.review.show()
        self.review.raise_()
        self.review.activateWindow()

    def stop_capture(self):
        if self.worker:
            self.toolbar.set_compact(False)
            self.toolbar.collapse_timer.stop()
            self.toolbar.stop_button.setEnabled(False)
            self.toolbar.pause_button.setEnabled(False)
            self.toolbar.status.setText('Finishing local processing...')
            self.worker.stop()

    def capture_error(self, message):
        self.statusBar().showMessage('Capture stopped: ' + message)
        QMessageBox.warning(self, 'Capture stopped', message + '\nYour collected draft is retained locally.')

    def capture_finished(self):
        finished_worker = self.worker
        if finished_worker:
            finished_worker.wait()
        self.worker = None
        if finished_worker:
            finished_worker.deleteLater()
        if self.toolbar:
            self.toolbar.close()
        self.start_button.setEnabled(True)
        self.persist()
        self.show()
        self.save_current()

    def save_current(self):
        if self.session is None:
            return
        dialog = SaveDialog(self.session, self)
        if not dialog.exec():
            self.persist()
            self.refresh()
            self.show_review()
            return
        try:
            self.store.save_paper(self.session, dialog.name.text(), dialog.metrics)
        except Exception as error:
            QMessageBox.critical(self, 'Save failed', f'{error}\nThe draft and recording have been retained.')
            self.persist()
            return
        try:
            self.store.cleanup_saved_session(self.session)
        except OSError as error:
            QMessageBox.warning(self, 'Paper saved', f'Paper saved, but temporary recording cleanup failed: {error}')
        self.session = None
        if self.review:
            self.review.close()
            self.review = None
        self.refresh()
        self.statusBar().showMessage('Paper saved locally.')

    def recover(self):
        if self.worker:
            self.show_review()
            return
        if self.session is None:
            drafts = sorted((self.store.root / 'sessions').glob('*/draft.json'), key=lambda p: p.stat().st_mtime, reverse=True)
            if not drafts:
                return
            dialog = QDialog(self)
            dialog.setWindowTitle('Recover a draft')
            layout = QVBoxLayout(dialog)
            choices = QComboBox()
            for path in drafts:
                choices.addItem(path.parent.name)
            layout.addWidget(choices)
            controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            controls.accepted.connect(dialog.accept)
            controls.rejected.connect(dialog.reject)
            layout.addWidget(controls)
            if not dialog.exec():
                return
            try:
                self.session = Session.read(drafts[choices.currentIndex()])
            except Exception as error:
                QMessageBox.warning(self, 'Cannot recover draft', str(error))
                return
        action = QMessageBox(self)
        action.setWindowTitle('Draft ready')
        action.setText(f'{len(self.session.questions)} questions retained. Choose what to do next.')
        edit = action.addButton('Review', QMessageBox.ButtonRole.ActionRole)
        resume = action.addButton('Resume recording', QMessageBox.ButtonRole.ActionRole)
        save = action.addButton('Save paper', QMessageBox.ButtonRole.AcceptRole)
        action.addButton(QMessageBox.StandardButton.Cancel)
        action.exec()
        if action.clickedButton() == edit:
            self.show_review()
        elif action.clickedButton() == resume:
            self.choose_region()
        elif action.clickedButton() == save:
            self.save_current()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.stop_capture()
            event.ignore()
            return
        if not self.persist():
            event.ignore()
            return
        if self.review:
            self.review.close()
        self.store.db.close()
        event.accept()
        QApplication.instance().quit()


def run():
    import sys
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName('CATalyst')
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
