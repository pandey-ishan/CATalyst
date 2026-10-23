import unittest
import cv2
import numpy as np
from cat_analyst.parser import Line, parse_test_provider
from cat_analyst.choice_marks import apply_choice_marks, green_ticks
from cat_analyst.core import analytics


def example(scale=1, combined=False, status='Skipped'):
    frame = np.full((900, 800, 3), 255, np.uint8)
    lines = [Line('03/22', 37, 15, 80, 29), Line('Find the value of x.', 37, 50, 400, 70)]
    for index, (option, value) in enumerate(zip('ABCD', ('13', '14', '15', '16'))):
        y = 116 + 88 * index
        if combined:
            lines.append(Line(f'{option} {value}', 67, y, 125, y + 20))
        else:
            lines += [Line(option, 67, y, 81, y + 20), Line(value, 107, y, 125, y + 20)]
    lines += [Line('Statistics Text Solution Video Solution', 60, 480, 480, 500),
              Line('Question Type A', 60, 565, 190, 585),
              Line('Attempt ' + status, 100, 660, 370, 680),
              Line('Accuracy -', 100, 700, 330, 720),
              Line('Time Taken 0:09 0:50 1:56', 100, 735, 600, 755)]
    if scale != 1:
        frame = cv2.resize(frame, None, fx=scale, fy=scale)
        lines = [Line(l.text, l.x*scale, l.y*scale, l.right*scale, l.bottom*scale) for l in lines]
    return frame, lines


def mark(frame, option=2, scale=1, shape='tick', x=741, y=None):
    center=(round(x*scale), round((126 + 88*option if y is None else y)*scale))
    radius=round(9*scale)
    color=(139, 204, 128)
    cv2.circle(frame, center, radius, color, -1, cv2.LINE_AA)
    if shape == 'solid':
        return
    points = np.array([[-5,0],[-2,3],[5,-4]]) if shape=='tick' else np.array([[-4,-4],[4,4]])
    points = np.rint(points*scale+center).astype(np.int32)
    cv2.polylines(frame,[points],False,(255,255,255),max(1,round(scale)),cv2.LINE_AA)
    if shape=='cross':
        points=np.rint(np.array([[-4,4],[4,-4]])*scale+center).astype(np.int32)
        cv2.polylines(frame,[points],False,(255,255,255),max(1,round(scale)),cv2.LINE_AA)


class ChoiceMarkTests(unittest.TestCase):
    def test_skipped_question_tick_is_answer_key_not_selected_response(self):
        frame, lines = example()
        mark(frame)
        q = parse_test_provider(lines, 800, 900)
        apply_choice_marks(q, lines, frame)
        self.assertEqual(q.correct_answer, 'C: 15')
        self.assertEqual(q.attempted, 'Unattempted')
        self.assertEqual(q.correctness, 'Unknown')
        self.assertEqual(q.selected_answer, '')
        self.assertEqual(q.seconds, 9)
        self.assertIsNone(analytics([q])[0]['accuracy'])

    def test_scaled_icons_and_combined_ocr_option_labels(self):
        for scale in (.8, 1.25, 1.5, 2):
            with self.subTest(scale=scale):
                frame, lines=example(scale, combined=True)
                mark(frame, scale=scale)
                q=parse_test_provider(lines)
                apply_choice_marks(q, lines, frame)
                self.assertEqual(q.correct_answer, 'C: 15')

    def test_answered_status_does_not_make_tick_the_users_choice(self):
        frame,lines=example(status='Answered')
        mark(frame)
        q=parse_test_provider(lines)
        apply_choice_marks(q, lines, frame)
        self.assertEqual(q.correct_answer, 'C: 15')
        self.assertEqual(q.selected_answer, '')
        self.assertEqual(q.correctness, 'Unknown')

    def test_solid_dot_and_cross_do_not_become_answer_ticks(self):
        for shape in ('solid','cross'):
            with self.subTest(shape=shape):
                frame,lines=example()
                mark(frame,shape=shape)
                q=parse_test_provider(lines)
                apply_choice_marks(q,lines,frame)
                self.assertEqual(q.correct_answer,'')

    def test_tick_in_statistics_is_not_an_option(self):
        frame,lines=example()
        mark(frame,y=670)
        q=parse_test_provider(lines)
        apply_choice_marks(q,lines,frame)
        self.assertEqual(q.correct_answer,'')

    def test_multiple_ticks_flag_ambiguity(self):
        frame,lines=example()
        mark(frame,option=1)
        mark(frame,option=2)
        q=parse_test_provider(lines)
        apply_choice_marks(q,lines,frame)
        self.assertEqual(q.correct_answer,'')
        self.assertTrue(any('Multiple' in w for w in q.warnings))

    def test_ocr_reading_tick_as_v_is_not_added_to_answer_text(self):
        frame,lines=example()
        mark(frame)
        lines.append(Line('V',735,295,747,309))
        q=parse_test_provider(lines)
        apply_choice_marks(q,lines,frame)
        self.assertEqual(q.correct_answer,'C: 15')

    def test_text_only_no_tick_does_not_guess_answer(self):
        frame,lines=example()
        q=parse_test_provider(lines)
        apply_choice_marks(q,lines,frame)
        self.assertEqual(q.correct_answer,'')


if __name__=='__main__':
    unittest.main()
