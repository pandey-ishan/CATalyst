import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile,unittest
from pathlib import Path
import cv2,numpy as np
from PySide6.QtWidgets import QApplication
from cat_analyst.core import Question,Session,Store,SECTIONS
from cat_analyst.parser import Line
from cat_analyst.image_fallback import fallback_regions,retain_fallbacks
from cat_analyst.reader import QuestionReader
APP=QApplication.instance() or QApplication([])
class FallbackTests(unittest.TestCase):
    def test_question_solution_crop_boundaries_and_reliable_text(self):
        lines=[Line('01/22',10,10,60,30),Line('Find x^2',10,50,200,80),Line('Statistics Text Solution',10,200,300,225),Line('x^2 = 4',10,250,200,280)]
        q=Question(1,text='Find x^2',solution='x^2 = 4')
        regions=fallback_regions(q,lines,400,500)
        self.assertEqual([r[0] for r in regions],['question','solution'])
        self.assertEqual(regions[0][-1],200);self.assertEqual(regions[1][2],229)
        self.assertEqual(fallback_regions(Question(1,text='Find x.'),lines,400,500),[])
    def test_compressed_deduped_images_survive_save_and_cleanup(self):
        with tempfile.TemporaryDirectory() as root:
            store=Store(Path(root));q=Question(1,text='x^2')
            q._fallback_regions=[('question',0,0,100,80),('solution',0,80,100,160)]
            session=Session(questions={1:q});directory=store.session_dir(session);directory.mkdir()
            frame=np.full((160,100,3),255,np.uint8);cv2.putText(frame,'x^2',(4,40),0,.6,(0,0,0),1)
            retain_fallbacks(q,frame,directory);retain_fallbacks(q,frame,directory)
            self.assertEqual(len(q.fallback_images),2)
            data=(directory/q.fallback_images[0]).read_bytes()
            self.assertLess(len(data),100*80*3)
            self.assertTrue(np.array_equal(cv2.imdecode(np.frombuffer(data,np.uint8),1),frame[:80]))
            session.dump(directory);self.assertEqual(Session.read(directory/'draft.json').questions[1].fallback_images,q.fallback_images)
            store.save_paper(session,'Mock',{s:dict(score=20,percentile=80) for s in SECTIONS})
            store.cleanup_saved_session(session)
            self.assertEqual(len(store.images(session.id,1)),2);self.assertFalse(directory.exists())
            self.assertEqual(store.questions()[0][2].fallback_images,[])
            store.delete_question(session.id,1);self.assertEqual(store.images(session.id,1),[]);store.db.close()
    def test_failure_preserves_draft_and_recording(self):
        with tempfile.TemporaryDirectory() as root:
            store=Store(Path(root));s=Session(questions={1:Question(1,fallback_images=['missing.png'])})
            directory=store.session_dir(s);directory.mkdir();(directory/'recording.avi').write_bytes(b'video')
            with self.assertRaises(FileNotFoundError):store.save_paper(s,'Mock',{k:dict(score=20,percentile=80) for k in SECTIONS})
            self.assertEqual(store.papers(),[]);self.assertTrue((directory/'recording.avi').exists());store.db.close()
    def test_reader_hides_solution_images_until_reveal(self):
        ok,data=cv2.imencode('.png',np.full((40,60,3),255,np.uint8))
        reader=QuestionReader([('Mock',Question(1))],image_records_loader=lambda q:[('auto-question-q1.png',data.tobytes()),('auto-solution-q1.png',data.tobytes())])
        self.assertIn('Question image',reader.browser.toPlainText());self.assertNotIn('Solution / captured image',reader.browser.toPlainText())
        reader.reveal.setChecked(True);self.assertIn('Solution / captured image',reader.browser.toPlainText());reader.close()
