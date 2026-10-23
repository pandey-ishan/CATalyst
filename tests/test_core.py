import json
import tempfile
import unittest
from pathlib import Path
from cat_analyst.core import Question, Session, Store, analytics, SECTIONS
from cat_analyst.parser import Line, parse_test provider


def lines(*texts):
    return [Line(text, 30, i * 40 + 20, 700, i * 40 + 42) for i, text in enumerate(texts)]


class ExtractionTests(unittest.TestCase):
    def test_statistics_and_solution_merge(self):
        stats = parse_test provider(lines('01/22', 'A shopkeeper offers a discount. What is n?',
            'Enter your response', '38', 'Backspace', 'Statistics Text Solution Video Solution',
            'Question Type A', 'Performance Parameter You Toppers Overall test takers',
            'Attempt Answered 87.5% 69.3%', 'Accuracy Incorrect 92.86% 82.65%',
            'Time Taken 3:10 1:28 2:40'))
        solution = parse_test provider(lines('01/22', 'A shopkeeper offers a discount. What is n?',
            'Enter your response', '38', 'Backspace', 'Correct Answer', '19',
            'Statistics Text Solution Video Solution', 'We have 2000n = 1900(n + 1).', 'Therefore n = 19.'))
        session = Session()
        session.merge(stats)
        session.merge(solution)
        q = session.questions[1]
        self.assertEqual(len(session.questions), 1)
        self.assertEqual(q.correct_answer, '19')
        self.assertEqual(q.selected_answer, '38')
        self.assertEqual(q.seconds, 190)
        self.assertEqual(q.correctness, 'Incorrect')
        self.assertEqual(q.difficulty, 'Easy')
        self.assertEqual(q.topic, 'Profit and Loss')
        self.assertIn('Therefore n = 19.', q.solution)
        self.assertEqual(q.missing(), [])

    def test_spatial_statistics_separate_columns(self):
        sample = lines('02/22', 'Find x.', 'Statistics Text Solution Video Solution', 'Question Type C')
        sample.extend([Line('Time Taken', 30, 200, 150, 220), Line('2:05', 300, 202, 350, 222),
                       Line('0:40', 440, 201, 490, 221), Line('1:20', 600, 200, 650, 220)])
        self.assertEqual(parse_test provider(sample).seconds, 125)
        self.assertEqual(parse_test provider(sample).difficulty, 'Hard')

    def test_no_identity_never_attaches_to_previous_question(self):
        self.assertIsNone(parse_test provider(lines('Correct Answer', '19', 'Text Solution', 'n = 19')))

    def test_manual_edits_and_conflicts(self):
        q = Question(1, text='Corrected text', locked=['text'], correct_answer='19')
        q.merge(Question(1, text='OCR text', correct_answer='18'))
        self.assertEqual(q.text, 'Corrected text')
        self.assertEqual(q.correct_answer, '19')
        self.assertTrue(any('Conflicting' in w for w in q.warnings))

    def test_repeat_fragments_are_not_duplicated(self):
        q = Question(1, solution='First line')
        q.merge(Question(1, solution='First line\nSecond line'))
        q.merge(Question(1, solution='First line'))
        self.assertEqual(q.solution, 'First line\nSecond line')

    def test_ocr_whitespace_variants_do_not_duplicate_question(self):
        q = Question(1, text='Rs. 2000, or Rs. 1900')
        q.merge(Question(1, text='Rs.2000,or Rs.1900'))
        self.assertEqual(q.text, 'Rs. 2000, or Rs. 1900')
        self.assertEqual(q.warnings, [])

    def test_unattempted_is_not_an_incorrect_answer(self):
        q = parse_test provider(lines('03/22', 'Find x.', 'Statistics Text Solution Video Solution',
                            'Question Type B', 'Attempt Not Answered 50%', 'Time Taken 0:05 1:00'))
        self.assertEqual(q.attempted, 'Unattempted')
        self.assertEqual(q.correctness, 'Unknown')
        self.assertNotIn('correctness', q.missing())
        self.assertIsNone(analytics([q])[0]['accuracy'])


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name))
        self.session = Session(questions={1: Question(1, text='Example', bookmark=True)})
        self.directory = self.store.session_dir(self.session)
        self.session.dump(self.directory)
        self.video = self.directory / 'recording-test.avi'
        self.video.write_bytes(b'temporary video')
        self.metrics = {s: {'score': 30, 'percentile': 90.5} for s in SECTIONS}

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def test_save_commit_precedes_cleanup_and_reopen(self):
        self.store.save_paper(self.session, 'SIMCAT', self.metrics)
        self.assertTrue(self.video.exists())
        self.store.cleanup_saved_session(self.session)
        self.assertFalse(self.video.exists())
        other = Store(Path(self.temp.name))
        self.assertEqual(other.papers()[0]['name'], 'SIMCAT')
        self.assertEqual(len(other.questions(bookmarks=True)), 1)
        other.db.close()

    def test_failed_save_retains_recording(self):
        with self.assertRaises(ValueError):
            self.store.save_paper(self.session, '', self.metrics)
        self.assertTrue(self.video.exists())
        with self.assertRaises(ValueError):
            self.store.cleanup_saved_session(self.session)
        self.assertTrue(self.video.exists())

    def test_optional_screenshot_failure_rolls_back_everything(self):
        self.session.keep_screenshots = True
        self.session.questions[1].screenshots = ['missing.png']
        with self.assertRaises(FileNotFoundError):
            self.store.save_paper(self.session, 'SIMCAT', self.metrics)
        self.assertEqual(self.store.papers(), [])
        self.assertTrue(self.video.exists())

    def test_screenshots_saved_only_when_enabled(self):
        image = self.directory / 'q1.png'
        image.write_bytes(b'example image')
        self.session.questions[1].screenshots = ['q1.png']
        self.store.save_paper(self.session, 'Text only', self.metrics)
        self.assertEqual(self.store.images(self.session.id, 1), [])
        self.session.keep_screenshots = True
        self.store.save_paper(self.session, 'With image', self.metrics)
        self.store.cleanup_saved_session(self.session)
        self.assertEqual(self.store.images(self.session.id, 1), [b'example image'])

    def test_draft_roundtrip_preserves_edits(self):
        self.session.questions[1].locked = ['text']
        self.session.dump(self.directory)
        restored = Session.read(self.directory / 'draft.json')
        self.assertEqual(restored.questions[1].locked, ['text'])

    def test_same_number_in_different_papers_is_distinct(self):
        self.store.save_paper(self.session, 'First', self.metrics)
        other = Session(questions={1: Question(1, text='Other')})
        self.store.save_paper(other, 'Second', self.metrics)
        self.assertEqual(len(self.store.questions()), 2)

    def test_unknown_values_are_not_zero_or_wrong(self):
        stats = analytics([Question(1, attempted='Answered', correctness='Correct', seconds=120),
                           Question(2, attempted='Answered'), Question(3)])[0]
        self.assertEqual(stats['accuracy'], 100)
        self.assertEqual(stats['graded'], 1)
        self.assertEqual(stats['attempts'], 2)
        self.assertEqual(stats['unknown_attempts'], 1)
        self.assertEqual(stats['average_seconds'], 120)


if __name__ == '__main__':
    unittest.main()
