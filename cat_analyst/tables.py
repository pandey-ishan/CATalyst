"""Readable comparison tables with rounded badges and meaningful status icons."""
import re
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QColor,QPainter,QPen
from PySide6.QtWidgets import QTableWidget,QTableWidgetItem,QStyledItemDelegate,QStyle,QHeaderView,QAbstractItemView,QWidget,QHBoxLayout,QToolButton
from .icons import line_icon

class ValueDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        painter.save();painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected=bool(option.state & QStyle.StateFlag.State_Selected)
        painter.fillRect(option.rect,QColor('#e9f2fd' if selected else '#fffdf8' if index.row()%2==0 else '#f7faff'))
        text=str(index.data() or '')
        header=index.model().headerData(index.column(),Qt.Orientation.Horizontal)
        rect=QRectF(option.rect).adjusted(8,11,-8,-11)
        bg,fg,icon='#edf3fc','#315c8b',None
        if text in ('Correct','Answered','Easy'):
            bg,fg,icon='#e4f4ed','#267454','check'
        elif text in ('Incorrect','Hard'):
            bg,fg,icon='#fff0e5','#9b4c20','alert'
        elif text in ('Unknown','Unattempted'):
            bg,fg='#eef0f4','#626b78'
        elif text=='Medium':bg,fg='#fff1de','#93591a'
        elif header in ('Time','Total time','Avg time'):
            icon='clock'
        elif header=='Bookmark' and text:icon='bookmark'
        badge=header in ('Difficulty','Attempt','Result','Time','Accuracy','Percentile','Overall','VARC','DILR','QA','Bookmark','Needs review') and bool(text)
        painter.setPen(Qt.PenStyle.NoPen)
        if badge:
            desired=option.fontMetrics.horizontalAdvance(text)+24+(20 if icon else 0)
            rect.setWidth(min(rect.width(),desired))
            painter.setBrush(QColor(bg));painter.drawRoundedRect(rect,11,11)
        text_rect=rect.adjusted(10 if badge else 3,0,-8,0)
        if icon:
            line_icon(icon,fg).paint(painter,int(text_rect.left()),int(rect.center().y()-8),16,16)
            text_rect.adjust(22,0,0,0)
        painter.setPen(QColor(fg if badge else '#263b50'))
        painter.drawText(text_rect,Qt.AlignmentFlag.AlignVCenter,option.fontMetrics.elidedText(text,Qt.TextElideMode.ElideRight,max(0,int(text_rect.width()))))
        if header in ('Accuracy','Percentile'):
            match=re.match(r'(\d+(?:\.\d+)?)',text)
            if match:
                track=QRectF(option.rect.left()+18,option.rect.bottom()-7,max(0,option.rect.width()-36),3)
                painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor('#dbe7f4'));painter.drawRoundedRect(track,1.5,1.5)
                track.setWidth(track.width()*min(100,float(match[1]))/100)
                painter.setBrush(QColor('#e58a42'));painter.drawRoundedRect(track,1.5,1.5)
        painter.restore()

class ReadableTable(QTableWidget):
    def __init__(self,headers,parent=None):
        super().__init__(0,len(headers),parent)
        self.setObjectName('readableTable');self.setHorizontalHeaderLabels(headers)
        self.setItemDelegate(ValueDelegate(self));self.setShowGrid(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.verticalHeader().hide();self.verticalHeader().setDefaultSectionSize(60)
        self.horizontalHeader().setMinimumSectionSize(85)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for i,title in enumerate(headers):
            if title in ('Paper','Topic','Question','Needs review'):
                self.horizontalHeader().setSectionResizeMode(i,QHeaderView.ResizeMode.Interactive)
                self.setColumnWidth(i,210 if title!='Question' else 300)
        self.actions=[]
        self.setMinimumWidth(0)
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and self.currentRow()>=0:
            self.cellDoubleClicked.emit(self.currentRow(),self.currentColumn())
        else:
            super().keyPressEvent(event)
    def set_actions(self, actions):
        self.actions=actions
        self.action_column=self.columnCount()
        self.setColumnCount(self.action_column+1)
        self.setHorizontalHeaderItem(self.action_column,QTableWidgetItem('Actions'))
        self.horizontalHeader().setSectionResizeMode(self.action_column,QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(self.action_column,126)
    def set_rows(self,rows):
        self.setRowCount(len(rows))
        for row,values in enumerate(rows):
            for col,value in enumerate(values):
                item=QTableWidgetItem(str(value));item.setToolTip(str(value));self.setItem(row,col,item)

        if self.actions:
            for row in range(len(rows)):
                box=QWidget();box.setObjectName('rowActions');layout=QHBoxLayout(box);layout.setContentsMargins(4,6,4,6);layout.setSpacing(4)
                for title,icon,callback in self.actions:
                    action=QToolButton();action.setIcon(line_icon(icon));action.setToolTip(title);action.setAccessibleName(title);action.setFixedSize(32,32)
                    action.clicked.connect(lambda checked=False,r=row,fn=callback:fn(r))
                    layout.addWidget(action)
                self.setCellWidget(row,self.action_column,box)
