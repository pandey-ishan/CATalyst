import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from cat_analyst.core import Question,Session
from cat_analyst.core import dashboard_insights
from cat_analyst.ui import ReviewWindow,STYLE
from cat_analyst.reader import QuestionReader
APP=QApplication.instance() or QApplication([])
APP.setStyleSheet(STYLE)
class CompactReviewTests(unittest.TestCase):
    def test_wrong_average_excludes_missing_times_and_skipped(self):
        qs=[Question(1,attempted='Answered',correctness='Incorrect',seconds=60),Question(2,attempted='Answered',correctness='Incorrect',seconds=180),Question(3,attempted='Answered',correctness='Incorrect'),Question(4,attempted='Unattempted',seconds=900)]
        result=dashboard_insights(qs)
        self.assertEqual(result['wrong_average'],120)
        self.assertEqual(result['wrong_timed'],2)
        self.assertIsNone(dashboard_insights([])['wrong_average'])
    def test_vertical_review_and_reader_fit_compact_width(self):
        q=Question(1,text='Find the value of x^{2}.',topic='Algebra')
        review=ReviewWindow(Session(questions={1:q}));review.show();APP.processEvents()
        self.assertLessEqual(review.width(),460)
        self.assertGreater(review.height(),review.width())
        self.assertEqual(review.table.horizontalScrollBar().maximum(),0)
        self.assertTrue(review.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        review.view(0);APP.processEvents()
        self.assertLessEqual(review.viewer.width(),520)
        self.assertGreater(review.viewer.browser.height(),100)
        review.viewer.close();review.close()
    def test_compact_reader_bookmark_and_navigation(self):
        reader=QuestionReader([('Mock',Question(1)),('Mock',Question(2))]);reader.show();APP.processEvents()
        reader.bookmark.click();self.assertTrue(reader.question.bookmark)
        reader.next.click();self.assertEqual(reader.question.number,2)
        reader.previous.click();self.assertEqual(reader.question.number,1)
        reader.close()
