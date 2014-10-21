import sys
import cre
import unittest
from mock import Mock
from test import re_tests


class TestParser(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_foo(self):
        pass


class TestRepetitionBehaviourWithCharacterExpression(unittest.TestCase):

    def setUp(self):
        self.c = cre.EvaluationContext("")

    def test_matches_dispatches_call_based_on_greed(self):
        e = cre.Expression()
        e._matches_greedy = Mock()
        e.matches(self.c)
        e._matches_greedy.assert_called_once_with(self.c)

        e._retry_greedy = Mock()
        e.retry(self.c)
        e._retry_greedy.assert_called_once_with(self.c)

        e._greedy = False
        e._matches_minimal = Mock()
        e.matches(self.c)
        e._matches_minimal.assert_called_once_with(self.c)

        e._retry_minimal = Mock()
        e.retry(self.c)
        e._retry_minimal.assert_called_once_with(self.c)

    def test_matches_updates_context(self):
        """Check for EvaluationContext._progress / ._matches"""
        self.c._subject = "a" * 8
        e = cre.CharacterExpression("a", name="foo")
        e.matches(self.c)
        self.assertEqual(self.c._progress, 1)

        e._max_repetitions = 2
        e.matches(self.c)
        self.assertEqual(self.c._progress, 3)

        e._max_repetitions = 5
        e.matches(self.c)
        self.assertEqual(self.c._progress, 8)

        self.assertEqual(self.c._matches, {"foo": [
            {"start": 0, "end": 1},
            {"start": 2, "end": 3},
            {"start": 7, "end": 8}
        ]})

    def test_matches_greedy_stores_all_results_for_later_use(self):
        """Check for Expression._results"""
        self.c._subject = "a" * 5
        e = cre.CharacterExpression("a", max_repetitions=2)
        e.matches(self.c)
        e.matches(self.c)
        e.matches(self.c)
        self.assertEqual(e._results, [
            [{"start": 0, "end": 1}, {"start": 1, "end": 2}],
            [{"start": 2, "end": 3}, {"start": 3, "end": 4}],
            [{"start": 4, "end": 5}]
        ])

    def test_matches_minimal_stores_all_results_for_later_use(self):
        """Check for Expression._results"""
        self.c._subject = "a" * 5
        e = cre.CharacterExpression("a", min_repetitions=2,
                                    max_repetitions=2)
        e.matches(self.c)
        e.matches(self.c)
        e.matches(self.c)
        self.assertEqual(e._results, [
            [{"start": 0, "end": 1}, {"start": 1, "end": 2}],
            [{"start": 2, "end": 3}, {"start": 3, "end": 4}]
        ])

    def test_retry_greedy_iterates_down_to_min_repetitions(self):
        self.c._progress = 5
        e = cre.CharacterExpression("a", min_repetitions=2,
                                    max_repetitions=4, name="foo")
        e._results = [[
            {"start": 0, "end": 1},
            {"start": 1, "end": 2},
            {"start": 2, "end": 3},
            {"start": 3, "end": 4}
        ]]
        self.c._matches["foo"] = [{"start": 3, "end": 4}]

        self.assertEqual(e.retry(self.c), True)
        self.assertEqual(self.c._matches["foo"],
                         [{"start": 2, "end": 3}])

        self.assertEqual(e.retry(self.c), True)
        self.assertEqual(self.c._matches["foo"],
                         [{"start": 1, "end": 2}])

        self.assertEqual(e.retry(self.c), False)
        self.assertEqual(self.c._matches, {})

    def test_retry_minimal_iterates_up_to_max_repetitions(self):
        return
        e = cre.CharacterExpression("a", min_repetitions=1,
                                    max_repetitions=3,
                                    greedy=False, name="foo")
        self.c._subject = "a" * 8
        e.matches(self.c)

        self.assertEqual(e.retry(self.c), True)
        self.assertEqual(self.c._matches["foo"],
                         [{"start": 1, "end": 2}])
        self.assertEqual(self.c._progress, 2)

        self.assertEqual(e.retry(self.c), True)
        self.assertEqual(self.c._matches["foo"],
                         [{"start": 2, "end": 3}])
        self.assertEqual(self.c._progress, 3)

        self.assertEqual(e.retry(self.c), False)
        self.assertEqual(self.c._matches, {})
        self.assertEqual(self.c._progress, 0)


class TestCharacterExpression(unittest.TestCase):

    def setUp(self):
        self.c = cre.EvaluationContext("abc")

    def test_matches_does_not_match_wrong_character(self):
        e = cre.CharacterExpression("b")
        e.matches(self.c)
        self.assertEqual(self.c.progress, 0)



class TestCompleteness(unittest.TestCase):
    """Test the library against the official pattern collection to check
    whether all scenarios are handled as expected.

    reference: https://hg.python.org/cpython/file/tip/Lib/test/re_tests.py

    """


if __name__ == "__main__":
    unittest.main()
