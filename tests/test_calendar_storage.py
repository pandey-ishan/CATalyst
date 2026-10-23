import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json,sqlite3,tempfile,unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock,patch
from PySide6.QtWidgets import QApplication,QMessageBox
from cat_analyst.core import Store,Session,Question,SECTIONS,today_local
from cat_analyst.ui import MainWindow,SaveDialog,FloatingToolbar
from cat_analyst.calendar_panel import MockCalendar,days_since_test
APP=QApplication.instance() or QApplication([])
METRICS={s:dict(score=30,percentile=90) for s in SECTIONS}

class CalendarStorageTests(unittest.TestCase):
    def test_legacy_database_migration_preserves_records(self):
        with tempfile.TemporaryDirectory() as root:
            db=sqlite3.connect(Path(root)/'analyst.sqlite3')
            db.execute('CREATE TABLE papers(id TEXT PRIMARY KEY,name TEXT,created TEXT,expected INTEGER,metrics TEXT)')
            db.execute('INSERT INTO papers VALUES(?,?,?,?,?)',('old','Older mock','2026-01-05T10:00:00',22,json.dumps(METRICS)))
            db.commit();db.close()
            store=Store(Path(root))
            self.assertEqual(store.papers()[0]['test_date'],'2026-01-05')
            self.assertEqual(store.papers()[0]['name'],'Older mock')
            store.db.close()

    def test_deletion_cascades_images_but_preserves_other_paper(self):
        with tempfile.TemporaryDirectory() as root:
            store=Store(Path(root))
            first=Session(questions={1:Question(1),2:Question(2)},expected=2)
            second=Session(questions={1:Question(1)},expected=1)
            for s in (first,second):store.save_paper(s,s.id,METRICS)
            with store.db:
                for n in (1,2):store.db.execute('INSERT INTO screenshots VALUES(?,?,?,?)',(first.id,n,f'{n}.png',b'test'))
            store.delete_question(first.id,1)
            self.assertEqual(store.images(first.id,1),[])
            self.assertEqual(len(store.questions(first.id)),1)
            self.assertEqual(next(p for p in store.papers() if p['id']==first.id)['expected'],2)
            store.delete_paper(first.id)
            self.assertEqual(store.images(first.id,2),[])
            self.assertEqual(len(store.questions()),1)
            self.assertEqual(store.papers()[0]['id'],second.id)
            store.db.close()

    def test_test_date_order_and_future_validation(self):
        with tempfile.TemporaryDirectory() as root:
            store=Store(Path(root))
            for age in (1,5):
                session=Session(test_date=(today_local()-timedelta(days=age)).isoformat(),questions={1:Question(1)})
                store.save_paper(session,str(age),METRICS)
            self.assertEqual([p['name'] for p in store.papers()],['5','1'])
            with self.assertRaises(ValueError):store.save_paper(Session(test_date=(today_local()+timedelta(days=1)).isoformat()),'Future',METRICS)
            store.db.close()

    def test_reminder_only_after_more_than_two_days(self):
        panel=MockCalendar()
        self.assertIsNone(days_since_test([]))
        for age in (0,2,3):
            papers=[dict(id='a',name='Test',test_date=(today_local()-timedelta(days=age)).isoformat())]
            panel.update_papers(papers)
            self.assertEqual(days_since_test(papers),age)
            self.assertEqual(panel.notification.isHidden(),age<=2)
        panel.close()

    def test_date_form_defaults_today_and_notch_collapses_without_stopping(self):
        form=SaveDialog(Session())
        self.assertEqual(form.test_date.date().toString('yyyy-MM-dd'),today_local().isoformat())
        form.close()
        owner=Mock();owner.paused=False;owner.worker=None
        notch=FloatingToolbar(owner)
        self.assertEqual(notch.collapse_timer.interval(),4000)
        notch.collapse_timer.timeout.emit()
        self.assertTrue(notch.compact)
        owner.stop_capture.assert_not_called()
        notch.pause_button.click();owner.toggle_pause.assert_called_once()
        notch.review_button.click();owner.show_review.assert_called_once()
        notch.toggle_size();self.assertFalse(notch.compact)
        notch.close()

    def test_delete_ui_requires_confirmation_and_refreshes(self):
        with tempfile.TemporaryDirectory() as root:
            main=MainWindow(Path(root));s=Session(questions={1:Question(1)})
            main.store.save_paper(s,'Example',METRICS);main.refresh();main.open_paper(s.id)
            with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.No):main.delete_selected_paper()
            self.assertEqual(len(main.store.papers()),1)
            with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):main.delete_selected_paper()
            self.assertEqual(main.store.papers(),[])
            self.assertEqual(main.dashboard.latest.text(),'No mocks saved yet')
            main.close()
