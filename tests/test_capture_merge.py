import unittest
from cat_analyst.core import Question,Session
from cat_analyst.parser import parse_test_provider,Line
from tests.test_core import lines

class CaptureMergeTests(unittest.TestCase):
    def test_scrolled_solution_never_extends_question(self):
        session=Session(questions={6:Question(6,text='Find the minimum value of the expression.')})
        view=parse_test_provider(lines('06/22','Given that,','(x - 1)^2 + 2kx + 11 = 0',
            'As the equation has no real roots, b^2 - 4ac < 0',
            'The largest possible integer that k can take is 4.',
            'Thus, k/4y + 9y = 1/y + 9y','Therefore, the required answer is 6.'))
        for _ in range(3):session.merge(view)
        self.assertEqual(len(session.questions),1)
        self.assertEqual(session.questions[6].text,'Find the minimum value of the expression.')
        self.assertEqual(session.questions[6].solution.count('Given that'),1)
        self.assertIn('required answer is 6',session.questions[6].solution)

    def test_unknown_scroll_fragment_is_preserved_only_in_raw(self):
        q=parse_test_provider(lines('06/22','(k - 1)^2 < 12','-2.46 < k < 4.46'))
        self.assertEqual(q.text,'')
        self.assertEqual(q.solution,'')
        self.assertIn('-2.46',q.raw_text)
        self.assertTrue(q.warnings)

    def test_fraction_in_solution_is_not_question_counter(self):
        self.assertIsNone(parse_test_provider(lines('Given that the equation has no real roots','1/22','Therefore the answer is 6.')))
        self.assertIsNone(parse_test_provider([Line('06/22',20,600,80,620)],800,900))

    def test_overlapping_scrolled_solutions_merge_in_both_directions(self):
        a='First step: expand the expression.\nThe discriminant must be less than zero.'
        b='The discriminant must be less than zero.\nTherefore, the answer is 6.'
        for first,second in [(a,b),(b,a)]:
            q=Question(6,solution=first)
            q.merge(Question(6,solution=second))
            q.merge(Question(6,solution=a))
            self.assertEqual(q.solution.count('The discriminant'),1)
            self.assertTrue(q.solution.startswith('First step'))
            self.assertTrue(q.solution.endswith('answer is 6.'))

    def test_small_ocr_typo_does_not_duplicate_question(self):
        original='A shopkeeper offers a discount on shoes. Find the price of 20 pairs at 1900 each.'
        q=Question(1,text=original)
        q.merge(Question(1,text=original.replace('shopkeeper','shopkeper')))
        self.assertEqual(q.text,original)

    def test_changed_math_is_not_silently_discarded(self):
        original='Find the minimum value of the expression when the price is 1900 per pair.'
        q=Question(1,text=original)
        q.merge(Question(1,text=original.replace('1900','1800')))
        self.assertIn('1800',q.text)
        self.assertTrue(q.warnings)

    def test_given_that_question_with_visible_tabs_stays_question(self):
        q=parse_test_provider(lines('06/22','Given that x has no real roots, find k.',
            'Statistics Text Solution Video Solution','Question Type A'))
        self.assertIn('find k',q.text)
        self.assertEqual(q.solution,'')
