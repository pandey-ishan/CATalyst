import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import time
import threading
import cv2
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont
from cat_analyst.capture import CaptureWorker
from cat_analyst.core import Question, Session, SECTIONS
from cat_analyst.ui import MainWindow, QuestionEditor, SaveDialog, ReviewWindow, STYLE

APP = QApplication.instance() or QApplication([])
APP.setQuitOnLastWindowClosed(False)
QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
APP.setFont(QFont('Segoe UI', 10))
APP.setStyle('Fusion')
APP.setStyleSheet(STYLE)


def wait_ms(milliseconds):
    end = time.monotonic() + milliseconds / 1000
    while time.monotonic() < end:
        APP.processEvents()
        time.sleep(.01)


class UiTests(unittest.TestCase):
    def test_dashboard_library_bookmark_and_editor(self):
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(Path(directory))
            self.assertEqual(window.cards['Saved mocks'].text(), '0')
            session = Session(questions={1: Question(1, text='Example question', bookmark=True)})
            metrics = {s: {'score': 30, 'percentile': 91.2} for s in SECTIONS}
            window.store.save_paper(session, 'UI smoke test', metrics)
            window.refresh()
            self.assertEqual(window.paper_table.rowCount(), 1)
            self.assertEqual(window.bookmark_table.rowCount(), 1)
            window.paper_table.selectRow(0)
            self.assertEqual(window.question_table.rowCount(), 1)
            editor = QuestionEditor(session.questions[1], window)
            editor.fields['text'].setPlainText('Manually corrected question')
            editor.fields['seconds'].setText('3:10')
            editor.save()
            self.assertEqual(session.questions[1].seconds, 190)
            self.assertIn('text', session.questions[1].locked)
            review = ReviewWindow(session, window)
            self.assertEqual(review.table.rowCount(), 1)
            save = SaveDialog(session, window)
            save.name.setText('Mock')
            save.ack.setChecked(True)
            for score, percentile in save.inputs.values():
                score.setText('30')
                percentile.setText('91.2')
            save.validate()
            self.assertEqual(save.result(), save.DialogCode.Accepted)
            window.show()
            APP.processEvents()
            artifacts = Path('_test_artifacts')
            artifacts.mkdir(exist_ok=True)
            window.grab().save(str(artifacts / 'dashboard.png'))
            window.close()


class FakeScreen:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def grab(self, region):
        return np.full((region['height'], region['width'], 4), 255, dtype=np.uint8)


class FakeWriter:
    def __init__(self, *args):
        self.frames = 0
        self.released = False

    def isOpened(self):
        return True

    def write(self, frame):
        self.frames += 1

    def release(self):
        self.released = True


class CaptureTests(unittest.TestCase):
    def test_pause_has_no_new_frames_resume_continues_same_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = FakeWriter()
            observations = []
            errors = []
            with patch('cat_analyst.capture.mss.mss', FakeScreen), \
                 patch('cat_analyst.capture.cv2.VideoWriter', return_value=writer), \
                 patch.object(CaptureWorker, 'own_window_active', return_value=False), \
                 patch.object(CaptureWorker, '_ocr', return_value=Question(1, text='Captured')):
                worker = CaptureWorker(dict(left=0, top=0, width=400, height=300), Path(directory), False)
                worker.observation.connect(observations.append)
                worker.failure.connect(errors.append)
                worker.start()
                wait_ms(1600)
                worker.pause(True)
                at_pause = writer.frames
                wait_ms(700)
                self.assertEqual(writer.frames, at_pause)
                worker.pause(False)
                wait_ms(1600)
                worker.stop()
                self.assertTrue(worker.wait(5000))
                APP.processEvents()
                self.assertFalse(errors, errors)
                self.assertGreater(writer.frames, at_pause)
                self.assertTrue(writer.released)
                self.assertGreaterEqual(len(observations), 2)
                self.assertFalse(list(Path(directory).glob('*.png')))


class CaptureFinalFrameTests(unittest.TestCase):
    def test_stop_drains_last_frame_and_writes_playable_local_video(self):
        with tempfile.TemporaryDirectory() as directory:
            started = threading.Event()
            release = threading.Event()
            observations = []
            errors = []

            def slow_ocr(frame):
                started.set()
                release.wait(5)
                return Question(2, text='Final frame')

            with patch('cat_analyst.capture.mss.mss', FakeScreen), \
                 patch.object(CaptureWorker, 'own_window_active', return_value=False), \
                 patch.object(CaptureWorker, '_ocr', side_effect=slow_ocr):
                worker = CaptureWorker(dict(left=0, top=0, width=400, height=300), Path(directory), True)
                worker.observation.connect(observations.append)
                worker.failure.connect(errors.append)
                worker.start()
                deadline = time.monotonic() + 4
                while not started.is_set() and time.monotonic() < deadline:
                    wait_ms(50)
                self.assertTrue(started.is_set())
                worker.stop()
                release.set()
                self.assertTrue(worker.wait(5000))
                APP.processEvents()
                self.assertFalse(errors)
                self.assertEqual(observations[0][1].number, 2)
                self.assertTrue(list(Path(directory).glob('*.png')))
                video = cv2.VideoCapture(str(next(Path(directory).glob('*.avi'))))
                ok, frame = video.read()
                video.release()
                self.assertTrue(ok)
                self.assertEqual(frame.shape[:2], (300, 400))

    def test_pause_invalidates_inflight_ocr(self):
        with tempfile.TemporaryDirectory() as directory:
            started = threading.Event()
            release = threading.Event()
            observations = []

            def slow_ocr(frame):
                started.set()
                release.wait(5)
                return Question(1)

            with patch('cat_analyst.capture.mss.mss', FakeScreen), \
                 patch('cat_analyst.capture.cv2.VideoWriter', return_value=FakeWriter()), \
                 patch.object(CaptureWorker, 'own_window_active', return_value=False), \
                 patch.object(CaptureWorker, '_ocr', side_effect=slow_ocr):
                worker = CaptureWorker(dict(left=0, top=0, width=400, height=300), Path(directory), False)
                worker.observation.connect(observations.append)
                worker.start()
                deadline = time.monotonic() + 4
                while not started.is_set() and time.monotonic() < deadline:
                    wait_ms(50)
                self.assertTrue(started.is_set())
                worker.pause(True)
                release.set()
                wait_ms(300)
                worker.stop()
                self.assertTrue(worker.wait(5000))
                APP.processEvents()
                self.assertEqual(observations, [])


if __name__ == '__main__':
    unittest.main()
