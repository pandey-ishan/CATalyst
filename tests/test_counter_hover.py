import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest,tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication
from cat_analyst.parser import Line,parse_test provider
from cat_analyst.core import Session,Question,SECTIONS,today_local
from cat_analyst.ui import MainWindow
from cat_analyst.calendar_panel import MockCalendar
APP=QApplication.instance() or QApplication([])
class CounterAndHoverTests(unittest.TestCase):
    def test_fourteen_counter_variants(self):
        for text in ('14/22','I4/22','l4/22','14 / 22'):
            q=parse_test provider([Line(text,20,10,80,30),Line('Find x.',20,70,150,90)],800,900)
            self.assertEqual(q.number,14)
        q=parse_test provider([Line('14',20,10,35,30),Line('/',37,10,42,30),Line('22',44,10,60,30),Line('Find x.',20,70,150,90)],800,900)
        self.assertEqual(q.number,14)
    def test_counter_requires_separator_and_valid_region(self):
        for text in ('1422','44/22','I4/word'):
            self.assertIsNone(parse_test provider([Line(text,20,10,80,30)],800,900))
        self.assertIsNone(parse_test provider([Line('I4/22',20,500,80,520)],800,900))
    def test_zero_days_and_full_bookmark_tooltip(self):
        panel=MockCalendar();panel.update_papers([dict(id='a',name='Mock',test_date=today_local().isoformat())])
        self.assertEqual(panel.recency.text(),'0 days');panel.close()
        with tempfile.TemporaryDirectory() as root:
            main=MainWindow(Path(root));text='Question content '*30+'<end>'
            main.store.save_paper(Session(questions={14:Question(14,text=text,bookmark=True)}),'Mock',{s:dict(score=25,percentile=80) for s in SECTIONS})
            main.refresh()
            self.assertIn('&lt;end&gt;',main.bookmark_table.item(0,0).toolTip())
            self.assertEqual(main.bookmark_table.columnCount(),5)
            main.close()
