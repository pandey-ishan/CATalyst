import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile,unittest
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from cat_analyst.tables import ReadableTable
from cat_analyst.ui import MainWindow
APP=QApplication.instance() or QApplication([])
class ReadableTableTests(unittest.TestCase):
    def test_columns_selection_and_single_keyboard_activation(self):
        table=ReadableTable(['QA #','Result','Time'])
        table.set_rows([(1,'Incorrect','3:10'),(2,'Correct','1:20')])
        table.show();table.selectRow(0)
        QTest.keyClick(table,Qt.Key.Key_Down)
        self.assertEqual(table.currentRow(),1)
        self.assertEqual(table.item(1,1).text(),'Correct')
        activated=[];table.cellDoubleClicked.connect(lambda row,col:activated.append(row))
        QTest.keyClick(table,Qt.Key.Key_Return)
        self.assertEqual(activated,[1])
        table.close()
    def test_icon_rail_keeps_labels_for_accessibility_and_navigation(self):
        with tempfile.TemporaryDirectory() as root:
            main=MainWindow(Path(root))
            self.assertEqual(main.navigation.width(),66)
            for index,title in enumerate(['Overview','Papers','Bookmarks']):
                item=main.navigation.item(index)
                self.assertEqual(item.text(),'')
                self.assertEqual(item.toolTip(),title)
                self.assertEqual(item.data(Qt.ItemDataRole.AccessibleTextRole),title)
                main.navigation.setCurrentRow(index)
                self.assertEqual(main.tabs.currentIndex(),index)
            main.close()
