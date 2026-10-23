import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest,tempfile,json
from pathlib import Path
from unittest.mock import Mock
import cv2
from PySide6.QtCore import QDate,QEvent
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QApplication,QToolButton
from cat_analyst.core import Session,Question,SECTIONS,today_local
from cat_analyst.ui import MainWindow,FloatingToolbar
from cat_analyst.calendar_panel import MockCalendar
from cat_analyst.choice_marks import apply_choice_marks,readable_option_frame
from cat_analyst.parser import Line,parse_test_provider
from tests.test_choice_marks import example,mark
APP=QApplication.instance() or QApplication([])
class RefinementTests(unittest.TestCase):
    def test_blue_fill_keeps_tick_answer_and_does_not_guess_selection(self):
        frame,lines=example(status='Answered')
        cv2.rectangle(frame,(45,275),(720,335),(200,115,30),-1)
        cv2.putText(frame,'C 15',(65,312),cv2.FONT_HERSHEY_SIMPLEX,0.7,(255,255,255),2)
        mark(frame)
        normalized=readable_option_frame(frame)
        self.assertTrue((normalized[280,50]==255).all())
        self.assertTrue((frame[280,50]!=normalized[280,50]).any())
        q=parse_test_provider(lines);apply_choice_marks(q,lines,frame)
        self.assertEqual(q.correct_answer,'C: 15');self.assertEqual(q.selected_answer,'')
    def test_stem_letter_does_not_break_option_list(self):
        frame,lines=example();mark(frame,option=1)
        lines.insert(2,Line('A sample question',67,75,350,95))
        q=parse_test_provider(lines);apply_choice_marks(q,lines,frame)
        self.assertEqual(q.correct_answer,'B: 14')
    def test_calendar_tooltip_has_scores_and_multiple_tests(self):
        panel=MockCalendar();stamp=today_local().isoformat()
        metrics=json.dumps({s:dict(score=25,percentile=80) for s in SECTIONS})
        panel.update_papers([dict(id=str(i),name=f'Mock {i}',test_date=stamp,metrics=metrics) for i in (1,2)])
        tip=panel.calendar.dateTextFormat(QDate.fromString(stamp,'yyyy-MM-dd')).toolTip()
        for value in ('Mock 1','Mock 2','Overall: 25','80 percentile'):self.assertIn(value,tip)
        panel.close()
    def test_notch_hover_expands_and_leave_restarts_timer(self):
        owner=Mock();owner.paused=False;owner.worker=None
        notch=FloatingToolbar(owner);notch.set_compact(True)
        from PySide6.QtCore import QPointF
        notch.enterEvent(QEnterEvent(QPointF(),QPointF(),QPointF()))
        self.assertFalse(notch.compact);self.assertFalse(notch.collapse_timer.isActive())
        notch.leaveEvent(QEvent(QEvent.Type.Leave));self.assertTrue(notch.collapse_timer.isActive())
        owner.stop_capture.assert_not_called();notch.close()
    def test_row_view_targets_the_clicked_question(self):
        with tempfile.TemporaryDirectory() as root:
            main=MainWindow(Path(root));session=Session(questions={1:Question(1),2:Question(2)})
            main.store.save_paper(session,'Mock',{s:dict(score=25,percentile=80) for s in SECTIONS})
            main.refresh();main.open_paper(session.id)
            actions=main.question_table.cellWidget(1,main.question_table.action_column)
            actions.findChildren(QToolButton)[0].click()
            self.assertEqual(main.saved_reader.question.number,2)
            main.saved_reader.close();main.close()
