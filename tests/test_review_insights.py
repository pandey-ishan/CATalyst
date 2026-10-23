import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase,QFont
from cat_analyst.core import Question,Session,SECTIONS
from cat_analyst.core import dashboard_insights
from cat_analyst.reader import math_html,question_html
from cat_analyst.reader import QuestionReader
from cat_analyst.ui import MainWindow,ReviewWindow,STYLE

APP=QApplication.instance() or QApplication([])
APP.setQuitOnLastWindowClosed(False)
QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
APP.setFont(QFont('Segoe UI',10));APP.setStyleSheet(STYLE)


class InsightTests(unittest.TestCase):
    def test_rankings_use_valid_sample_sizes_and_exclude_skipped_timing(self):
        qs=[]
        for i in range(3):
            qs.append(Question(i,topic='Algebra',attempted='Answered',correctness='Incorrect',seconds=240))
            qs.append(Question(i+3,topic='Geometry',attempted='Answered',correctness='Correct',seconds=120))
        qs += [Question(7,topic='Algebra',attempted='Unattempted',seconds=1),
               Question(8,topic='Probability',attempted='Answered',correctness='Incorrect',seconds=900),
               Question(9,topic='Unclassified',attempted='Answered',correctness='Incorrect',seconds=999)]
        result=dashboard_insights(qs)
        self.assertEqual([r['topic'] for r in result['weak_accuracy']],['Algebra','Geometry'])
        self.assertEqual(result['slow_topics'][0]['average'],240)
        self.assertEqual(result['slow_topics'][0]['count'],3)
        self.assertEqual(result['weak_accuracy'][0]['graded'],3)

    def test_empty_and_unknown_values_are_not_zero_performance(self):
        result=dashboard_insights([Question(1)])
        self.assertIsNone(result['attempt_rate'])
        self.assertIsNone(result['attempt_average'])
        self.assertIsNone(result['summary']['accuracy'])
        self.assertEqual(result['weak_accuracy'],[])
        self.assertEqual(result['wrong_timed'],0)

    def test_review_queue_and_easy_misses(self):
        result=dashboard_insights([Question(1,difficulty='Easy',attempted='Unattempted',bookmark=True),
            Question(2,difficulty='Easy',attempted='Answered',correctness='Incorrect',seconds=90),
            Question(3,difficulty='Easy',attempted='Unknown')])
        self.assertEqual(result['easy_misses'],2)
        self.assertEqual(result['bookmarks'],1)
        self.assertEqual(result['wrong_seconds'],90)
        self.assertEqual(result['attempt_rate'],50)


class FormattingTests(unittest.TestCase):
    def test_compound_negative_and_nested_exponents(self):
        rendered=math_html('2^{2+4+2x} = (0.125)^{-80}; x^(n+(1)); y^2')
        self.assertIn('<sup>2+4+2x</sup>',rendered)
        self.assertIn('<sup>-80</sup>',rendered)
        self.assertIn('<sup>n+(1)</sup>',rendered)
        self.assertIn('y<sup>2</sup>',rendered)

    def test_ocr_html_is_escaped_instead_of_loading_resources(self):
        result=math_html('<img src="https://example.com/a"> x^{<script>}')
        self.assertNotIn('<img',result)
        self.assertNotIn('<script>',result)
        self.assertIn('&lt;img',result)

    def test_options_are_readable_and_incomplete_notation_is_preserved(self):
        result=question_html('Find x.\nA 13\nB 14\nC 15\nD 16')
        self.assertEqual(result.count('<table'),4)
        self.assertIn('x^{2',math_html('x^{2'))


class ReaderTests(unittest.TestCase):
    def test_live_reader_does_not_end_recording_and_bookmarks_persist(self):
        with tempfile.TemporaryDirectory() as root:
            main=MainWindow(Path(root))
            main.session=Session(questions={3:Question(3,text='Find x^{2}.')})
            worker=Mock();worker.isRunning.return_value=False;main.worker=worker
            main.show_review()
            main.review.view_button.click()
            viewer=main.review.viewer
            self.assertTrue(viewer.isVisible())
            self.assertFalse(viewer.isModal())
            worker.stop.assert_not_called()
            self.assertIs(main.worker,worker)
            viewer.toggle_bookmark()
            draft=Session.read(main.store.session_dir(main.session)/'draft.json')
            self.assertTrue(draft.questions[3].bookmark)
            viewer.close();main.worker=None;main.close()

    def test_reading_navigation_and_answer_reveal(self):
        first=Question(1,text='Find 2^{n+1}.',correct_answer='8',solution='n = 2')
        second=Question(2,text='Next question')
        reader=QuestionReader([('Mock A',first),('Mock A',second)])
        self.assertNotIn('Text solution',reader.browser.toPlainText())
        self.assertIn('vertical-align:super',reader.browser.toHtml())
        reader.reveal.setChecked(True)
        self.assertIn('n = 2',reader.browser.toPlainText())
        reader.navigate(1)
        self.assertIs(reader.question,second)
        self.assertFalse(reader.reveal.isChecked())
        reader.close()

    def test_dashboard_cards_open_saved_topic_reader(self):
        with tempfile.TemporaryDirectory() as root:
            main=MainWindow(Path(root))
            session=Session(questions={i:Question(i,topic='Algebra',attempted='Answered',correctness='Incorrect',seconds=180) for i in range(1,4)})
            metrics={s:dict(score=30,percentile=90) for s in SECTIONS}
            main.store.save_paper(session,'Mock A',metrics);main.refresh()
            main.view_topic('Algebra')
            self.assertEqual(len(main.saved_reader.entries),3)
            main.saved_reader.toggle_bookmark()
            self.assertEqual(len(main.store.questions(bookmarks=True)),1)
            main.saved_reader.close();main.close()


if __name__=='__main__':unittest.main()
