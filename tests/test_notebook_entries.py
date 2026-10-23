import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from cat_analyst.entries import EntryList
APP=QApplication.instance() or QApplication([])
class NotebookEntriesTests(unittest.TestCase):
    def test_keyboard_selection_activation_and_safe_text(self):
        entries=EntryList(['Paper','Date'])
        entries.set_rows([['First','2026-10-01'],['<img src="https://invalid">','2026-10-02']])
        entries.show();entries.selectRow(0)
        QTest.keyClick(entries,Qt.Key.Key_Down)
        self.assertEqual(entries.currentRow(),1)
        activated=[];entries.cellDoubleClicked.connect(lambda row,col:activated.append(row))
        QTest.keyClick(entries,Qt.Key.Key_Return)
        self.assertEqual(activated,[1])
        index=entries.model().index(1,0)
        doc=entries.itemDelegate().document(index,400)
        self.assertIn('<img src=',doc.toPlainText())
        entries.close()
    def test_long_entry_wraps_on_narrow_view(self):
        entries=EntryList(['Paper','Description'])
        entries.set_rows([['Mock', 'Detailed text '*40]])
        index=entries.model().index(0,0)
        delegate=entries.itemDelegate()
        self.assertGreater(delegate.document(index,300).size().height(),delegate.document(index,900).size().height())
        entries.close()
