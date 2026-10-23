"""Local vector line icons, independent of OS theme and emoji fonts."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon,QPixmap,QPainter
from PySide6.QtSvg import QSvgRenderer

PATHS = {
    'edit':'<path d="m4 16 12-12 4 4L8 20H4zM14 6l4 4"/>',
    'delete':'<path d="M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7"/>',

    'check':'<path d="m5 12 4 4L19 6"/>',
    'alert':'<circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 17h.01"/>',
    'clock':'<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
    'overview':'<circle cx="7" cy="7" r="3"/><circle cx="17" cy="7" r="3"/><circle cx="7" cy="17" r="3"/><circle cx="17" cy="17" r="3"/>',
    'papers':'<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h4"/>',
    'bookmark':'<path d="M6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16l-6-4z"/>',
    'play':'<path d="m8 4 12 8-12 8z"/>',
    'pause':'<path d="M8 4v16M16 4v16"/>',
    'review':'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    'plus':'<path d="M12 5v14M5 12h14"/>',
    'recover':'<path d="M4 10a8 8 0 1 1 1 8M4 4v6h6"/>',
    'chart':'<path d="M4 3v17h17M8 15l4-5 4 2 5-7"/>',
}

def line_icon(name, color='#4275a8'):
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</svg>'
    pixmap=QPixmap(48,48);pixmap.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pixmap);QSvgRenderer(svg.encode()).render(painter);painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)
