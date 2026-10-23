"""Rounded notebook entries with native selection and keyboard navigation."""
import html
from PySide6.QtCore import Qt,Signal,QSize,QRectF,QRect
from PySide6.QtGui import QColor,QPainter,QIcon,QTextDocument,QAbstractTextDocumentLayout
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QToolButton,QListWidget,QListWidgetItem,QStyledItemDelegate,QStyle,QAbstractItemView

from .icons import line_icon

class EntryDelegate(QStyledItemDelegate):
    def document(self,item,width):
        headers,values=item.data(Qt.ItemDataRole.UserRole)
        title=str(values[0]) if headers[0]!='QA #' else 'Question '+str(values[0]).zfill(2)
        details=' &nbsp; · &nbsp; '.join('<b>'+html.escape(str(k))+'</b> '+html.escape(str(v)) for k,v in zip(headers[1:],values[1:]) if str(v))
        doc=QTextDocument();doc.setDocumentMargin(0)
        doc.setDefaultStyleSheet('body {font-family:Segoe UI;color:#282d2a;font-size:13px;} h3 {font-size:18px;font-weight:600;margin:0 0 9px 0;} p {line-height:145%;margin:0;color:#646a62;} b {font-weight:500;color:#414a43;}')
        doc.setHtml('<body><h3>'+html.escape(title)+'</h3><p>'+details+'</p></body>')
        doc.setTextWidth(max(100,width-46))
        return doc

    def paint(self,painter,option,index):
        painter.save();painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=QRectF(option.rect).adjusted(3,4,-3,-4)
        selected=bool(option.state & QStyle.StateFlag.State_Selected)
        painter.setPen(QColor('#8a9e8e' if selected else '#deddd3'))
        painter.setBrush(QColor('#e5ece3' if selected else '#fffdf7'))
        painter.drawRoundedRect(rect,18,18)
        painter.translate(rect.left()+20,rect.top()+16)
        doc=self.document(index,option.rect.width())
        doc.documentLayout().draw(painter,QAbstractTextDocumentLayout.PaintContext())
        painter.restore()

    def sizeHint(self,option,index):
        width=self.parent().viewport().width()
        doc=self.document(index,width)
        return QSize(100,max(96,int(doc.size().height())+40))

class EntryList(QListWidget):
    cellDoubleClicked=Signal(int,int)
    def __init__(self,headers,parent=None):
        super().__init__(parent);self.headers=headers
        self.setObjectName('entryList');self.setSpacing(3)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setItemDelegate(EntryDelegate(self))
        self.itemActivated.connect(lambda item:self.cellDoubleClicked.emit(self.row(item),0))
        self.setMinimumWidth(0)
    def set_rows(self,rows):
        self.clear()
        for values in rows:
            item=QListWidgetItem();item.setData(Qt.ItemDataRole.UserRole,(self.headers,list(values)))
            item.setText(' '.join(str(v) for v in values))
            item.setToolTip('\n'.join(f'{k}: {v}' for k,v in zip(self.headers,values)))
            self.addItem(item)
    def rowCount(self):return self.count()
    def selectRow(self,row):self.setCurrentRow(row)
    def setRowCount(self,count):
        if count==0:self.clear()
    def resizeEvent(self,event):
        super().resizeEvent(event);self.scheduleDelayedItemsLayout()


class CompactReviewList(EntryList):
    def __init__(self,headers):
        super().__init__(headers);self.actions=[]
    def set_actions(self,actions):self.actions=actions
    def set_rows(self,rows):
        self.clear()
        for row,values in enumerate(rows):
            item=QListWidgetItem();item.setData(Qt.ItemDataRole.UserRole,(self.headers,list(values)));item.setSizeHint(QSize(100,154));self.addItem(item)
            card=QWidget();card.setObjectName('liveQuestionCard')
            layout=QVBoxLayout(card);layout.setContentsMargins(12,10,12,10);layout.setSpacing(5)
            title=QLabel(f'Q{values[0]}  |  {values[1]}');title.setWordWrap(True);title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);layout.addWidget(title)
            detail=QLabel(f'{values[2]}  |  {values[3]}  |  {values[4]}  |  {values[5]}');detail.setWordWrap(True);detail.setObjectName('subtitle');detail.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);layout.addWidget(detail)
            bottom=QHBoxLayout();state=QLabel(str(values[6]));state.setWordWrap(True);state.setObjectName('subtitle');state.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);bottom.addWidget(state,1)
            for name,icon,callback in self.actions:
                action=QToolButton();action.setIcon(line_icon(icon));action.setToolTip(name);action.setAccessibleName(name);action.setFixedSize(30,30)
                action.clicked.connect(lambda checked=False,r=row,fn=callback:fn(r));bottom.addWidget(action)
            layout.addLayout(bottom);self.setItemWidget(item,card)


class NavigationDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=option.rect.adjusted(5,4,-5,-4)
        selected=bool(option.state & QStyle.StateFlag.State_Selected)
        hovered=bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected or hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#ffead7' if selected else '#dbeaff'))
            painter.drawRoundedRect(rect,16,16)
        icon=index.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(icon,QIcon):
            target=QRect(0,0,20,20)
            target.moveCenter(option.rect.center())
            icon.paint(painter,target,Qt.AlignmentFlag.AlignCenter)
        painter.restore()
    def sizeHint(self,option,index):
        return QSize(64,52)
