"""Explicitly centered icon-only navigation, independent of label padding."""
from PySide6.QtCore import Qt,QRect,QSize
from PySide6.QtGui import QPainter,QColor,QIcon
from PySide6.QtWidgets import QStyledItemDelegate,QStyle

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
