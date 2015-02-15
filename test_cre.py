import sys
import cre
import unittest
from mock import Mock
from test import re_tests


class TestRepetitionBehaviourWithCharacterExpression(unittest.TestCase):

    def setUp(self):
        self.c = cre.EvaluationContext("")

    def test_matches_updates_context(self):
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
        self.c._subject = "a" * 5
        e = cre.CharacterExpression("a", max_repetitions=2)
        e.matches(self.c)
        e.matches(self.c)
        e.matches(self.c)
        self.assertEqual(e._matches, [
            [{"start": 0, "end": 1}, {"start": 1, "end": 2}],
            [{"start": 2, "end": 3}, {"start": 3, "end": 4}],
            [{"start": 4, "end": 5}]
        ])

    def test_matches_nongreedy_stores_all_results_for_later_use(self):
        self.c._subject = "a" * 5
        e = cre.CharacterExpression("a", min_repetitions=2,
                                    max_repetitions=2)
        e.matches(self.c)
        e.matches(self.c)
        e.matches(self.c)
        self.assertEqual(e._matches, [
            [{"start": 0, "end": 1}, {"start": 1, "end": 2}],
            [{"start": 2, "end": 3}, {"start": 3, "end": 4}]
        ])

    def test_retry_greedy_iterates_down_to_min_repetitions(self):
        self.c._progress = 5
        e = cre.CharacterExpression("a", min_repetitions=2,
                                    max_repetitions=4, name="foo")
        e._matches = [[
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

    def test_retry_nongreedy_iterates_up_to_max_repetitions(self):
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

    def test_unnamed_expression_does_not_store_result_in_context(self):
        e = cre.CharacterExpression("a")
        e.matches(self.c)
        self.assertEqual(self.c._matches, {})


class TestCharacterExpression(unittest.TestCase):

    def setUp(self):
        self.c = cre.EvaluationContext("abc")

    def test_expression_matches_correct_character(self):
        e = cre.CharacterExpression("a")
        self.assertEqual(e._matches_once(self.c), {"start": 0, "end": 1})

    def test_expression_does_not_match_wrong_character(self):
        e = cre.CharacterExpression("b")
        self.assertEqual(e._matches_once(self.c), None)


class TestCharacterRangeExpression(unittest.TestCase):

    def setUp(self):
        self.c = cre.EvaluationContext("")

    def test_expression_matches_all_characters_in_range(self):
        e = cre.CharacterRangeExpression("a", "c")
        self.c._subject = "a"
        self.assertEqual(e._matches_once(self.c), {"start": 0, "end": 1})
        self.c._subject = "b"
        self.assertEqual(e._matches_once(self.c), {"start": 0, "end": 1})
        self.c._subject = "c"
        self.assertEqual(e._matches_once(self.c), {"start": 0, "end": 1})

    def test_expression_does_not_match_wrong_characters(self):
        e = cre.CharacterRangeExpression("d", "f")
        self.c._subject = "a"
        self.assertEqual(e._matches_once(self.c), None)

    def test_named_expression_doesnt_push_match_if_match_is_empty(self):
        # test correct behaviour in GroupExpression.matches()
        # pattern := "(?P<foo>b)?b"
        # subject := "b"
        c = cre.EvaluationContext("b")
        e = cre.GroupExpression(
            (
                cre.CharacterExpression("a", min_repetitions=0, name="foo"),
                cre.CharacterExpression("b"),
            )
        )
        self.assertEqual(e.matches(c), True)

        # test correct behaviour in GroupExpression.retry()
        # pattern := "(?P<foo>b)?b"
        # subject := "b"
        c = cre.EvaluationContext("b")
        e = cre.GroupExpression(
            (
                cre.CharacterExpression("b", min_repetitions=0, name="foo"),
                cre.CharacterExpression("b"),
            )
        )
        self.assertEqual(e.matches(c), True)


class TestAnyOfOptionsExpression(unittest.TestCase):

    def setUp(self):
        self.c = cre.EvaluationContext("abcd")
        children = (cre.Expression(), cre.Expression(), cre.Expression())
        children[0]._matches_once = Mock(side_effect=({"start": 0, "end": 1}, None, None, None))
        children[1]._matches_once = Mock(side_effect=({"start": 1, "end": 2}, None, None))
        children[2]._matches_once = Mock(side_effect=({"start": 2, "end": 3}, None))
        self.e = cre.AnyOfOptionsExpression(children)

    def test_expression_tries_children_in_order(self):
        self.assertEqual(self.e.matches(self.c), True)
        self.assertEqual(self.e.matches(self.c), True)
        self.assertEqual(self.e.matches(self.c), True)
        self.assertEqual(self.e.matches(self.c), False)
        self.assertEqual(self.c._progress, 3)

    def test_only_matching_option_changes_state(self):
        self.e._children[0]._matches_once.side_effect = (None,)
        self.e.matches(self.c)
        self.assertEqual(self.e._children[0]._matches, [])
        self.assertEqual(self.e._children[1]._matches, [[{"start": 1, "end": 2}]])
        self.assertEqual(self.e._children[2]._matches, [])

    def test_retry_resets_state_of_all_children(self):
        """todo: properly define the behaviour of this expression!
        Look at the following examples:

        pattern := "((ab)|a)b"
        subject := "ab"
        The pattern should match the subject because the AnyOfOptionsExpression
        does not necessarily have to consume the "b".
        """
        return
        self.e._max_repetitions = 2
        self.assertEqual(self.e.matches(self.c), True)
        self.assertEqual(self.e._matches, [[
            {"start": 0, "end": 1, "matching_child": self.e._children[0]},
            {"start": 1, "end": 2, "matching_child": self.e._children[1]}]])
        self.assertEqual(self.e._children[0]._matches, [[{"start": 0, "end": 1}]])
        self.assertEqual(self.e._children[1]._matches, [[{"start": 1, "end": 2}]])
        self.assertEqual(self.e._children[2]._matches, [])

        self.assertEqual(self.e.retry(self.c), True)
        self.assertEqual(self.e._matches, [[{"start": 0, "end": 1}]])
        self.assertEqual(self.e._children[0]._matches, [[{"start": 0, "end": 1}]])
        self.assertEqual(self.e._children[1]._matches, [])
        self.assertEqual(self.e._children[2]._matches, [])

        self.assertEqual(self.e.retry(self.c), False)
        self.assertEqual(self.e._children[0]._matches, [[{"start": 0, "end": 1}]])
        self.assertEqual(self.e._children[1]._matches, [])
        self.assertEqual(self.e._children[2]._matches, [])

        self.assertEqual(self.e.retry(self.c), False)
        self.assertEqual(self.e._children[0]._matches, [])
        self.assertEqual(self.e._children[1]._matches, [])
        self.assertEqual(self.e._children[2]._matches, [])


class TestBackReferenceExpression(unittest.TestCase):

    def setUp(self):
        self.c = cre.EvaluationContext("")
        self.c._matches["foo"] = [{"start": 0, "end": 1}]

    def test_matches_once_matches_previous_group_result(self):
        self.c._subject = "aaa"
        self.c._progress = 1
        e = cre.BackReferenceExpression("foo")
        self.assertEqual(e._matches_once(self.c), {"start": 1, "end": 2})


class TestGroupExpression(unittest.TestCase):

    def setUp(self):
        self.c = cre.EvaluationContext("abcd")
        children = (cre.Expression(), cre.Expression(), cre.Expression())
        children[0]._matches_once = Mock(side_effect=({"start": 0, "end": 1}, None, None, None))
        children[1]._matches_once = Mock(side_effect=({"start": 1, "end": 2}, None, None))
        children[2]._matches_once = Mock(side_effect=({"start": 2, "end": 3}, None))
        self.e = cre.GroupExpression(children)

    def test_expression_evaluates_all_children_in_order(self):
        self.assertEqual(self.e.matches(self.c), True)
        self.assertEqual(self.e._children[0]._matches, [[{"start": 0, "end": 1}]])
        self.assertEqual(self.e._children[1]._matches, [[{"start": 1, "end": 2}]])
        self.assertEqual(self.e._children[2]._matches, [[{"start": 2, "end": 3}]])
        self.assertEqual(self.e._matches, [[{"start": 0, "end": 3}]])

    def test_matches_resets_child_expressions_on_failure(self):
        self.e._children[2]._matches_once.side_effect = (None,)
        self.assertEqual(self.e.matches(self.c), False)
        self.assertEqual(self.e._children[0]._matches, [])
        self.assertEqual(self.e._children[1]._matches, [])
        self.assertEqual(self.e._children[2]._matches, [])
        self.assertEqual(self.e._matches, [])

    def test_retry_greedy_iterates_children_to_find_valid_match(self):
        """
        subject := "a" * 16
        pattern := "^(a+a{2,}a){3,}a$"
        """
        inf = float("inf")
        c = cre.EvaluationContext("a" * 16)
        e = cre.GroupExpression(
            (
                cre.GroupExpression(
                    (
                        cre.CharacterExpression("a", max_repetitions=inf),
                        cre.CharacterExpression("a", min_repetitions=2, max_repetitions=inf),
                        cre.CharacterExpression("a")
                    ),
                    min_repetitions=3,
                    max_repetitions=inf
                ),
                cre.CharacterExpression("a")
            )
        )
        self.assertEqual(e.matches(c), True)

    def test_retry_greedy_pops_children_to_find_valid_match(self):
        """
        subject := "a" * 10
        pattern := "^(aaa)+a{2,}$"
        """
        inf = float("inf")
        c = cre.EvaluationContext("a" * 10)
        e = cre.GroupExpression(
            (
                cre.GroupExpression(
                    (cre.CharacterExpression("a"),cre.CharacterExpression("a"),cre.CharacterExpression("a"),),
                    min_repetitions=1,
                    max_repetitions=float("inf")
                ),
                cre.CharacterExpression("a", min_repetitions=2, max_repetitions=inf)
            )
        )
        self.assertEqual(e.matches(c), True)

    def test_retry_nongreedy_iterates_children_to_find_valid_match(self):
        """
        subject := "a" * 12 + b
        pattern := "^(aaa){2,}?b$"
        """
        c = cre.EvaluationContext("a" * 12 + "b")
        e = cre.GroupExpression(
            (
                cre.GroupExpression(
                    (cre.CharacterExpression("a"),cre.CharacterExpression("a"),cre.CharacterExpression("a"),),
                    min_repetitions=2,
                    max_repetitions=float("inf"),
                    greedy=False
                ),
                cre.CharacterExpression("b")
            )
        )
        self.assertEqual(e.matches(c), True)

    def test_group_can_handle_expressions_that_dont_match_because_min_repetitions_is_zero(self):
        """
        subject := "bb"
        pattern := "(a?bc?)b"
        """
        c = cre.EvaluationContext("bb")
        e = cre.GroupExpression(
            (
                cre.GroupExpression((
                    cre.CharacterExpression("a", min_repetitions=0),
                    cre.CharacterExpression("b"),
                    cre.CharacterExpression("c", min_repetitions=0))
                ),
                cre.CharacterExpression("b")
            )
        )
        self.assertEqual(e.matches(c), True)


class TestParser(unittest.TestCase):

    def setUp(self):
        self.p = cre.Parser()

    def tearDown(self):
        pass

    def test_parsing_of_simple_character_pattern(self):
        self.assertEqual(self.p.parse("abc"), cre.GroupExpression(children=(
            cre.CharacterExpression("a"),
            cre.CharacterExpression("b"),
            cre.CharacterExpression("c")
        )))

    def test_parsing_of_simple_conjunction(self):
        self.assertEqual(self.p.parse("(ab)c"), cre.GroupExpression(children=(
            cre.GroupExpression(children=(
                cre.CharacterExpression("a"),
                cre.CharacterExpression("b")
            )),
            cre.CharacterExpression("c")
        )))

    def test_resolve_repetitions_handles_all_repetition_indicators(self):
        inf = float("inf")
        assertions = (
            ("*",  {"greedy": True,  "min_repetitions": 0, "max_repetitions": inf}),
            ("*?", {"greedy": False, "min_repetitions": 0, "max_repetitions": inf}),
            ("+",  {"greedy": True,  "min_repetitions": 1, "max_repetitions": inf}),
            ("+?", {"greedy": False, "min_repetitions": 1, "max_repetitions": inf}),
            ("?",  {"greedy": True,  "min_repetitions": 0, "max_repetitions": 1}),
            ("??", {"greedy": False, "min_repetitions": 0, "max_repetitions": 1}),

            ("{2}",  {"greedy": True,  "min_repetitions": 2, "max_repetitions": 2}),
            ("{2}?", {"greedy": False, "min_repetitions": 2, "max_repetitions": 2}),

            ("{2,5}",  {"greedy": True,  "min_repetitions": 2, "max_repetitions": 5}),
            ("{2,5}?", {"greedy": False, "min_repetitions": 2, "max_repetitions": 5}),
            ("{12,15}",  {"greedy": True,  "min_repetitions": 12, "max_repetitions": 15}),
            ("{12,15}?", {"greedy": False, "min_repetitions": 12, "max_repetitions": 15}),
            ("{,}",  {"greedy": True,  "min_repetitions": 0, "max_repetitions": inf}),
            ("{,}?", {"greedy": False, "min_repetitions": 0, "max_repetitions": inf}),
        )
        for a in assertions:
            self.p._context = cre.EvaluationContext(a[0])
            self.assertEqual(self.p._resolve_repetitions(), a[1])


class TestCompleteness(unittest.TestCase):
    """Test the library against the official pattern collection to check
    whether all scenarios are handled as expected.

    reference: https://hg.python.org/cpython/file/tip/Lib/test/re_tests.py

    """


if __name__ == "__main__":
    unittest.main()
