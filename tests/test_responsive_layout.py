import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication
from cat_analyst.ui import MainWindow,STYLE
from cat_analyst.core import Session,Question,SECTIONS
APP=QApplication.instance() or QApplication([])
APP.setStyleSheet(STYLE)

class ResponsiveLayoutTests(unittest.TestCase):
    def test_startup_fits_available_screen(self):
        screen=Mock();screen.availableGeometry.return_value=QRect(0,0,1280,720)
        with tempfile.TemporaryDirectory() as root, patch.object(QApplication,'primaryScreen',return_value=screen):
            window=MainWindow(Path(root));window.show();APP.processEvents()
            self.assertLessEqual(window.width(),1280)
            self.assertLessEqual(window.height(),680)
            self.assertGreaterEqual(window.x(),0)
            self.assertGreaterEqual(window.y(),0)
            window.close()

    def test_cards_reflow_without_horizontal_clipping_and_icons_exist(self):
        with tempfile.TemporaryDirectory() as root:
            window=MainWindow(Path(root))
            window.store.save_paper(Session(questions={1:Question(1)}),'Long mock title '*20,{s:dict(score=20,percentile=75) for s in SECTIONS})
            window.refresh();window.show()
            for width in (1024,1280,1440):
                window.resize(width,720)
                for _ in range(5):APP.processEvents()
                self.assertEqual(window.width(),width)
                self.assertLessEqual(window.dashboard.widget().width(),window.dashboard.viewport().width())
                for grid,widgets,_ in window.dashboard.responsive_groups:
                    for card in widgets:
                        self.assertGreaterEqual(card.x(),0)
                        self.assertLessEqual(card.geometry().right(),window.dashboard.widget().width())
            for i in range(3):self.assertFalse(window.navigation.item(i).icon().isNull())
            window.close()
