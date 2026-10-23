"""Local mock calendar and in-app recency reminder."""
from datetime import date
import json
from PySide6.QtCore import QDate,Qt,Signal,QEvent,QRect
from PySide6.QtGui import QColor,QTextCharFormat,QPainter
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QCalendarWidget,QPushButton,QFrame,QTableView,QToolTip
from .core import today_local


def days_since_test(papers,today=None):
    today=today or today_local()
    dates=[date.fromisoformat(p.get('test_date') or p['created'][:10]) for p in papers]
    past=[d for d in dates if d<=today]
    return (today-max(past)).days if past else None


class NotebookCalendar(QCalendarWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.date_rects={}
        self.grid=self.findChild(QTableView)
        self.grid.viewport().installEventFilter(self)
        self.currentPageChanged.connect(lambda *args:self.date_rects.clear())
    def eventFilter(self,watched,event):
        if event.type()==QEvent.Type.ToolTip:
            day=next((day for day,rect in self.date_rects.items() if rect.contains(event.pos())),None)
            text=self.dateTextFormat(day).toolTip() if day else ''
            if text:QToolTip.showText(event.globalPos(),text,self)
            else:QToolTip.hideText()
            return True
        return super().eventFilter(watched,event)

    def paintCell(self,painter,rect,day):
        self.date_rects[day]=QRect(rect)
        painter.save();painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        marked=self.dateTextFormat(day).background().color()
        selected=day==self.selectedDate()
        has_mock=self.dateTextFormat(day).toolTip()!=''
        if selected or has_mock:
            painter.setBrush(QColor('#ffe2ca' if selected else '#e5f0ff'))
            painter.drawRoundedRect(rect.adjusted(2,2,-2,-2),9,9)
        enabled=day<=self.maximumDate() and day>=self.minimumDate()
        painter.setPen(QColor('#395f86' if enabled and day.month()==self.monthShown() else '#a0afbf'))
        painter.drawText(rect,Qt.AlignmentFlag.AlignCenter,str(day.day()))
        painter.restore()


class MockCalendar(QFrame):
    paper_requested=Signal(str)

    def __init__(self,parent=None):
        super().__init__(parent);self.setObjectName('panel');self.setFixedWidth(280)
        layout=QVBoxLayout(self);layout.setContentsMargins(14,18,14,18)
        heading=QLabel('Your mock calendar');heading.setObjectName('sectionTitle');layout.addWidget(heading)
        self.recency=QLabel();self.recency.setObjectName('metric');self.recency.setWordWrap(True);layout.addWidget(self.recency)
        self.caption=QLabel('Since your last test');self.caption.setObjectName('subtitle');layout.addWidget(self.caption)
        self.notification=QLabel();self.notification.setObjectName('warning');self.notification.setWordWrap(True);layout.addWidget(self.notification)
        self.calendar=NotebookCalendar();self.calendar.setGridVisible(False)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.SingleLetterDayNames)
        self.calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self.calendar.setSelectedDate(QDate.fromString(today_local().isoformat(),'yyyy-MM-dd'))
        self.calendar.setMaximumDate(QDate.fromString(today_local().isoformat(),'yyyy-MM-dd'))
        self.calendar.setMinimumWidth(240);self.calendar.setMaximumHeight(235)
        self.calendar.selectionChanged.connect(self.show_day)
        self.calendar.setNavigationBarVisible(False)
        navigation=QHBoxLayout()
        previous=QPushButton();previous.setText('Previous');previous.setToolTip('Previous month');previous.clicked.connect(self.calendar.showPreviousMonth)
        following=QPushButton();following.setText('Next');following.setToolTip('Next month');following.clicked.connect(self.calendar.showNextMonth)
        self.month_title=QLabel();self.month_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        navigation.addWidget(previous);navigation.addWidget(following)
        layout.addWidget(self.month_title);layout.addLayout(navigation)
        self.calendar.currentPageChanged.connect(lambda year,month:self.month_title.setText(QDate(year,month,1).toString('MMMM yyyy')))
        self.month_title.setText(QDate(self.calendar.yearShown(),self.calendar.monthShown(),1).toString('MMMM yyyy'))
        layout.addWidget(self.calendar)
        self.day_heading=QLabel();self.day_heading.setObjectName('subtitle');layout.addWidget(self.day_heading)
        self.entries=QVBoxLayout();layout.addLayout(self.entries)
        layout.addStretch()
        tip=QLabel('Shaded dates mark completed mocks.\nChoose a date to open its papers.');tip.setWordWrap(True);tip.setObjectName('subtitle');layout.addWidget(tip)
        self.papers=[];self.marked=[]

    def update_papers(self,papers):
        self.papers=papers
        elapsed=days_since_test(papers)
        self.recency.setText('Start today' if elapsed is None else '0 days' if elapsed==0 else f'{elapsed} day'+('s' if elapsed!=1 else ''))
        self.caption.setText('Save a mock to begin tracking' if elapsed is None else 'Since your last test')
        self.notification.setVisible(elapsed is not None and elapsed>2)
        self.notification.setText(f'It has been {elapsed} days since your last mock. Plan your next test when you are ready.' if elapsed is not None else '')
        for day in self.marked:self.calendar.setDateTextFormat(day,QTextCharFormat())
        self.marked=[]
        groups={}
        for paper in papers:
            detail=paper['name']
            metrics=json.loads(paper.get('metrics','{}'))
            for section,values in metrics.items():
                detail+=f"\n{section}: {values['score']:g} score | {values['percentile']:g} percentile"
            groups.setdefault(paper.get('test_date') or paper['created'][:10],[]).append(detail)
        for stamp,names in groups.items():
            day=QDate.fromString(stamp,'yyyy-MM-dd');format=QTextCharFormat()
            format.setBackground(QColor('#e5f0ff'));format.setForeground(QColor('#365a82'));format.setToolTip('\n\n'.join(names))
            self.calendar.setDateTextFormat(day,format);self.marked.append(day)
        self.calendar.setMaximumDate(QDate.fromString(today_local().isoformat(),'yyyy-MM-dd'))
        self.show_day()

    def show_day(self):
        while self.entries.count():
            item=self.entries.takeAt(0)
            if item.widget():item.widget().hide();item.widget().deleteLater()
        stamp=self.calendar.selectedDate().toString('yyyy-MM-dd')
        self.day_heading.setText(self.calendar.selectedDate().toString('dd MMM yyyy'))
        papers=[p for p in self.papers if (p.get('test_date') or p['created'][:10])==stamp]
        for paper in papers:
            action=QPushButton();action.setText(action.fontMetrics().elidedText(paper['name'],Qt.TextElideMode.ElideRight,215));action.setToolTip(paper['name']);action.setObjectName('topicRow')
            action.clicked.connect(lambda checked=False,pid=paper['id']:self.paper_requested.emit(pid));self.entries.addWidget(action)
        if not papers:
            empty=QLabel('No test saved on this date.');empty.setObjectName('subtitle');empty.setWordWrap(True);self.entries.addWidget(empty)
