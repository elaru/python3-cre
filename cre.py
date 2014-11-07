#!/usr/local/bin/python3
"""cre - custom regular expressions

This module provides a custom regex implementation I wrote to get a
better understanding of regular expressions. It aims to support the
full feature set of pythons builtin re module excluding unicode
support in character groups (e.g. "\w" will not match the japanese
alphabet). It is not optimized for speed and should not be used in
production code.
If you want to see how the module works, read the docstrings of the
Expression and Parser classes.

- Philipp Schiffmann

"""

import unicodedata


class EvaluationContext:
    """The evaluation context holds information about the current parsing state
    during runtime. This includes the subject, current parsing progress and the
    results of capturing expressions.
    """

    def __init__(self, subject):
        # Number of parsed characters; changed by expressions during evaluation
        self._progress = 0

        # String that is being parsed
        self._subject = subject

        # Matches of capturing groups; used by BackReferenceExpressions and
        # returned as the result of successful matching operation.
        self._matches = {}

    @property
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, value):
        self._progress = value

    @property
    def subject(self):
        return self._subject

    @property
    def remaining_subject(self):
        if self._progress >= len(self._subject):
            raise ParsingOverflowException()
        return self._subject[self._progress:]

    @property
    def current_subject_character(self):
        if self._progress >= len(self._subject):
            raise ParsingOverflowException()
        return self._subject[self._progress]

    @property
    def matches(self):
        return self._matches

    def push_match(self, name, value):
        self._matches.setdefault(name, []).append(value)

    def override_match(self, name, value):
        self._matches[name][-1] = value

    def pop_match(self, name):
        self._matches[name].pop()
        if not len(self._matches[name]):
            del self._matches[name]

    @property
    def flattened_matches(self):
        return dict(map(lambda x: (x[0], x[1][-1]),
                        self._matches.items()))

    def get_match_string(self, group):
        last_result = self.matches[group][-1]
        return self._subject[last_result["start"]:last_result["end"]]

    def get_match_range(self, group):
        return self.matches[group][-1]


class Expression:
    """Base class for all expressions.

    Expression subclasses should not be instantiated directly, but can
    be generated by the Parser from a regular expression pattern string.

    Expressions form an object tree that is evaluated recursively. Every
    expression has a method matches() that works on an EvaluationContext
    object and tries to match itself against the contexts subject.

    """

    def __init__(self, min_repetitions=1, max_repetitions=1,
                 greedy=True, name=None):
        self._min_repetitions = min_repetitions
        self._max_repetitions = max_repetitions
        self._greedy = greedy
        self._name = name
        self._matches = []

    @property
    def _current_match(self):
        return self._matches[-1]

    def _pop_current_match(self, context):
        if self._name is not None:
            context.pop_match(self._name)
        self._matches.pop()

    @property
    def _current_repetition(self):
        return self._current_match[-1]

    @_current_repetition.setter
    def _current_repetition(self, v):
        self._current_match[-1] = v

    def matches(self, context):
        """Check whether the expression matches in the assigned context.

        Add every match result to self._matches for later use and update
        the context progress. If the expression has a name, update the
        context to store the last match.
        Return True if the expression matches, else False.

        """
        # Remember the progress in case we have to reset it because the
        # expression did not match
        progress = context.progress

        # Temporary list of results; append it to self._matches if the
        # evaluation was successful
        matches = []

        # Try to match the expression up to upper_limit times
        upper_limit = (self._min_repetitions,
                       self._max_repetitions)[self._greedy]

        while (context.progress < len(context.subject)
               and len(matches) < upper_limit):
            match = self._matches_once(context)
            if match is None:
                break
            matches.append(match)
            context.progress = match["end"]

        if len(matches) < self._min_repetitions:
            # The expression couldn't match as often as specified: reset
            # the context, discard the matches, return False
            context.progress = progress
            return False

        self._matches.append(matches)
        if self._name != None:
            # If the expression was a numeric or named group, update
            # the matched value on the context
            context.push_match(self._name, _copykeys(
                            self._current_repetition, ("start", "end")))
        return True

    def retry(self, context):
        """Reevaluate the expression with a different repetition.

        This method is required for scenarios like:
        pattern := "f\w+ar"
        subject := "foobar"

        In this case, the sequence expression "\w+" will match the
        string "oobar" which causes the following character expression
        "a" to fail. Now we have to iterate through the remaining match
        variations of the sequence expression ("ooba", "oob", "oo", "o")
        to find a combination that is valid for subsequent expressions.

        This method performs a single iteration step. This includes
        updating the context progress and, if the expression is named,
        the context match dict.

        Note that the iteration can be performed in two directions:
        If the expression is greedy, it consumes as many characters as
        possible during the initial evaluation and we free parts of the
        subject during reevaluation.
        if the expression is non-greedy, it matches as few characters as
        possible during the initial evaluation and we consume additional
        parts of the subject during reevaluation.

        Return True if reevaluation was successful and the new
        repetition count is valid or False if the reevaluation
        failed, for example because it overflowed the repetition
        limits.

        """
        # These methods return True if the expression could be
        # reevaluated, or False otherwise. The methods already
        # update self._matches and the context progress.
        if not ((self._retry__iterate_nongreedy,
                 self._retry__iterate_greedy)[self._greedy])(context):
            self.undo(context)
            return False

        if self._name is not None:
            # Update the context if this is a named group.
            context.override_match(self._name,
                        _copykeys(self._current_repetition, ("start", "end")))
        return True

    def undo(self, context):
        """Undo the last match with all repetitions."""
        if len(self._current_match):
            context.progress = self._current_match[0]["start"]
        self._pop_current_match(context)

    def _retry__iterate_greedy(self, context):
        """Try to undo the last iteration.

        Helper method for retry(); Execute a single repetition iteration
        with greedy behaviour.
        If the expression allows for fewer repetitions, remove the last
        match from internal stack, reassign the consumed characters to
        the context and return True.
        If the expression already matches as few times as allowed, drop
        the matches and return False.

        """
        if len(self._current_match) > self._min_repetitions:
            context.progress = self._current_match.pop()["start"]
            return True
        return False

    def _retry__iterate_nongreedy(self, context):
        """Try to match one additional time.

        Helper method for retry(); Execute a single repetition iteration
        with nongreedy behaviour.
        Execute _matches_once(). If the expression matches again and has
        not yet matched as often as allowed, return True, else return
        False.

        """
        if len(self._matches[-1]) < self._max_repetitions:
            match = self._matches_once(context)
            if match is not None:
                # Expression matches, add new match to internal stack
                self._matches[-1].append(match)
                context.progress = match["end"]
                return True
        return False

    def _matches_once(self, context):
        """Evaluate the expression once without modifying state.

        Check whether the expression matches the subject inside the
        context beginning at context.progress without evaluating
        repetitions. Return None if the expression did not match, else
        a dict with keys "start" and "end" pointing to the respective
        indices in subject.

        """
        raise NotImplementedError()


class CharacterExpression(Expression):
    """Represents a single character."""

    def __init__(self, character, **kwargs):
        super().__init__(**kwargs)
        self._char = character

    def _matches_once(self, context):
        if context.current_subject_character == self._char:
            return {"start": context.progress, "end": context.progress + 1}
        return None


class CharacterRangeExpression(Expression):
    """Represents a character range, like [a-z]. For a collection of
    ranges, like [a-zA-Z], multiple range expressions are concatenated
    in a GroupExpression."""

    def __init__(self, start, end, **kwargs):
        super().__init__(**kwargs)
        self._start = start
        self._end = end

    def _matches_once(self, context):
        if self._start <= context.current_subject_character <= self._end:
            return {"start": context.progress, "end": context.progress + 1}
        return None


class AnyOfOptionsExpression(Expression):
    """Represents a logical-or expression with two or more values.

    This class will be instantiated for
    the following expression strings:
    * Two expressions concatenated with "|"
    * Character groups like "[abc]" or "\w", which will be
      represented as an option group of  CharacterExpressions
      or CharacterRangeExpressions.

    """

    def __init__(self, options, **kwargs):
        super().__init__(**kwargs)
        self._options = options

    def _matches_once(self, context):
        """Evaluate each option in order until the first one matches."""
        start = context.progress
        for o in self._options:
            if o.matches(context):
                return {"start": start,
                        "end": context.progress,
                        "matching_child": o}
        return None


class GroupExpression(Expression):
    """Represents a group of expressions."""

    def __init__(self, children, **kwargs):
        super().__init__(**kwargs)
        self._children = children

    def matches(self, context):
        """Check whether the expression matches in the assigned context.
        """
        progress = context.progress
        self._matches.append([])
        upper_limit = (self._min_repetitions,
                       self._max_repetitions)[self._greedy]

        while True:
            while (context.progress < len(context.subject)
                   and len(self._current_match) < upper_limit):
                match = self._matches_once(context)
                if match is None:
                    break
                self._current_match.append(match)
            if len(self._current_match) >= self._min_repetitions:
                break
            if not self._reevaluate_one_repetition(context):
                # _reevaluate_one_repetition already reset the
                # expression, so we can simply abort here.
                return False

        if self._name != None:
            context.push_match(self._name, _copykeys(
                            self._current_repetition, ("start", "end")))
        return True

    def undo(self, context):
        """Undo all children, then proceed with default behaviour."""
        for _ in self._current_match:
            for c in reversed(self._children):
                c.undo()
        super().undo(context)

    def _matches_once(self, context):
        """Execute all child expressions in order.

        Iterate recursively over self._children to find a combination
        that suffices the match conditions of all children. Look at the
        following example:

        pattern := "a+?a{1,3}b"
        subject := "aaaaab"

        Here, the expression "a+?" is evaluated first and consumes the
        string "a". After that, the expression "a{1,3}" consumes the
        string "aaa". Now the remaining subject is "ab", but the last
        pattern matches "b".
        Our approach to solve this is to reevaluate the expressions in
        reverse order. We start with the last matching expression and
        retry it until the next expression matches or all possibilities
        failed. Then we retry the second last expression and start
        reevaluating the last one, and so on.
        Look at the following table; the ranges address the indices in
        the subject:

        iteration | "a+?" | "a{1,3}" | "b"
            #0        -         -       -
            #1        0         -       -
            #2        0       1 - 3     -
            #3        0       1 - 2     -
            #4        0         1       -
            #5      0 - 1       -       -
            #6      0 - 1     2 - 4     -
            #7      0 - 1     2 - 4     5

        If the expression does not match, the iterative calls to retry
        will automatically reset the child expressions.

        """
        def __match_one_child(child):
            """Perform the actual recursion."""
            if child >= len(self._children):
                # Reached the end of child list, exit
                return True
            current = self._children[child]
            if not current.matches(context):
                # Can't match, let previous expression retry
                return False
            while not __match_one_child(child + 1):
                if not current.retry(context):
                    # Can't match, let previous expression retry
                    return False
            return True

        if __match_one_child(0):
            return {"start": self._children[0]._current_match[0]["start"],
                    "end": self._children[-1]._current_repetition["end"]}
        return None

    def _retry__iterate_greedy(self, context):
        """Retry children, then retry repetitons, then pop repetitions.

        The default behaviour to retry an expression is to simply free
        the last repetition and check whether the new repetition count
        is still within _min_repetitions and _max_repetitions. However,
        for group expressions we take another approach first.

        Only if these steps fails we free the last repetition.

        """

        if len(self._current_match) == 0:
            # Abort prematurely so we don't retry child matches that
            # don't belong to this match.
            return False

        initial_repetitions = len(self._current_match)
        if self._reevaluate_one_repetition(context):
            return True

        if initial_repetitions == self._min_repetitions:
            # We can't pop another result or we don't have enough
            # repetitions; abort
            return False

        for _ in range(0, initial_repetitions - 1):
            # __retry_one_repetition returned False which means that
            # __retry_one_child was executed on each repetition, so
            # all results have been reset. Restore them up to the second
            # last repetition.
            self._current_match.append(self._matches_once(context))
        return True

    def _retry__iterate_nongreedy(self, context):
        raise NotImplementedError("Still todo.")

    def _reevaluate_one_repetition(self, context):
        """Reevaluate child expressions to find the next valid match.

        This method checks whether there is another valid combination of
        child matches with the same amount of repetitions. This is done
        by reevaluating all children, beginning with the last child and
        proceeding backwards.
        The retry method automatically reverts all state on failure, so
        if a child can't retry, it reassigns its consumed part of the
        subject to the context so the next child can use it for its turn
        on retry again.
        Once a child successfully reevaluates, we walk the child list
        back up and call matches() on each. If this fails again, we
        repeat the previous step. This way iterate the children up and
        down until we find a new valid match combination or the first
        child in the group can't retry anymore, which indicates that we
        have tried every combination.
        Remember that retry() reverts the expression on failure, which
        means once the algorithm can't find another combination, the
        repetition is already completely reversed. All that needs to be
        done now is to pop the last repetition from the group
        expression.
        This behaviour is encapsulated in the internal function
        __retry_one_child(child).

        But! We're not done yet. The last paragraph just described our
        approach for a single repetition. To find all combinations of
        this group expression, we also need to take previous repetitions
        into account.
        Luckily, __match_one_child showed us how to do that: We iterate
        the repetition list up and down and call __match_one_child on
        each until we find another combination.
        To iterate backwards we call __match_one_child. If it returns
        False, we pop the last repetition from the group expression and
        just call it again. If it returns True, we call _matches_once
        on self to iterate forwards.

        This method completely reverts any state if the reevaluation
        fails, including the context progress, the context match
        reference and self._current_match.

        """
        def __retry_one_child(child):
            if child < 0:
                return False
            current = self._children[child]
            if current.retry(context):
                return True
            while __retry_one_child(child - 1):
                if current.matches(context):
                    return True
            return False

        if not len(self._current_match):
            self._pop_current_match(context)
            return False
        if __retry_one_child(len(self._children) - 1):
            self._current_repetition = {
                "start": self._children[0]._current_match[0]["start"],
                "end": self._children[-1]._current_repetition["end"]}
            return True
        self._current_match.pop()
        while self._reevaluate_one_repetition(context):
            result = self._matches_once(context)
            if result is not None:
                self._current_match.append(result)
                return True
        return False


class BackReferenceExpression(Expression):
    """"""

    def __init__(self, reference, **kwargs):
        super().__init__(**kwargs)
        self._reference = reference

    def _matches_once(self, context):
        pattern = context.get_match_string(self._reference)
        if context.remaining_subject.startswith(pattern):
            return {"start": context.progress,
                    "end": context.progress + len(pattern)}
        return None


class Parser:
    """The parser creates expression object trees from pattern strings."""

    def __init__(self):
        self._context = None
        self._stack = []

    @property
    def _current(self):
        return self._stack[-1]

    @_current.setter
    def _current(self, value):
        self._stack.append(value)

    def _pop_current(self):
        return self._stack.pop()

    def parse(self, pattern):
        if self._context is not None:
            raise Exception("Parser already in use!")
        self._context = EvaluationContext(pattern)
        self._current = {"state": "unknown"}

        while self._context.progress < len(pattern):
            getattr(self, "_parse_" + self._current["state"])()

        if len(self._stack) > 1:
            raise Exception("More expressions opened than closed")
        root = GroupExpression(self._groups.pop()["children"])
        self._context = None
        return root

    def _parse_unknown(self):
        """"""
        if self._context.current_subject_character == "\\":
            self._current = {"state": "escaped"}
        elif self._context.current_subject_character == "[":
            self._current = {"state": "character_group",
                             "closing_tag": "]"}
        elif self._context.current_subject_character == "(":
            self._current = {"state": "group",
                             "closing_tag": ")"}
        else:
            self._current = {"state": "character"}

    def _parse_character(self):
        """Handle parsing when a character expression was detected."""
        args = {"character": self._context.current_subject_character}
        self._context.progress += 1
        args.update(self._resolve_repetitions())
        self._pop_current()
        self._current["children"].append(CharacterExpression(**args))

    def _parse_character_group(self):
        pass

    def _parse_group(self):
        if self._context.current_subject_character == ")":
            self._context.progress += 1
            args = {"children": self._current["children"]}
            args.update(self._resolve_repetitions())
            self._pop_current()
            self._current["children"].append(GroupExpression(**args))
            return
        if self._context.current_subject_character == ":":
            capturing = False
            self._context.progress += 1

    def _parse_escaped(self):
        """Handle parsing after an escape sequence (backslash) was detected.

        This method will either create an appropriate expression tree for
        patterns like "\w" or prepare parsing of the next character as
        CharacterExpression.

        """
        if self._context.current_subject_character == "s":
            self._context.progress += 1
            args = {"options": (CharacterExpression(" "),
                                CharacterExpression("\t"),
                                CharacterExpression("\n"),
                                CharacterExpression("\r"),
                                CharacterExpression("\f"),
                                CharacterExpression("\v"))}
            args.update(self._resolve_repetitions())
            self._pop_current()
            self._current["children"].append(AnyOfOptionsExpression(**args))
        # todo: cover the remaining escaped groups, like \w or \W
        else:
            self._current = {
                "state": "character",
                "character": self._context.current_subject_character}

    def _resolve_repetitions(self):
        """Read repetitions and greed from the current position.

        Return a dict with keys greedy, min_repetitions and
        max_repetitions, like the named parameters for Expression,
        filled with resolved or default values.

        todo: handle repetitions indications like {1,} or {5}

        """
        minimum, maximum, greedy = 1, 1, True
        inf = float("inf")
        progress = self._context.progress

        if self._context.progress >= len(self._context._subject):
            # The caller already consumed the remaining subject; don't
            # read any further.
            return {"min_repetitions": minimum,
                    "max_repetitions": maximum,
                    "greedy": greedy}
        elif self._context.current_subject_character == "+":
            minimum = 1
            maximum = inf
            self._context.progress += 1
        elif self._context.current_subject_character == "?":
            minimum = 0
            maximum = 1
            self._context.progress += 1
        elif self._context.current_subject_character == "*":
            minimum = 0
            maximum = inf
            self._context.progress += 1

        # expression object for pattern "{(?P<repetition>\d+)}"
        elif GroupExpression((
                    CharacterExpression(character="{"),
                    GroupExpression((CharacterRangeExpression(start="0",
                                                end="9",max_repetitions=inf),),
                                    name="repetition"),
                    CharacterExpression("}"))
             ).matches(self._context):
                minimum = int(self._context.get_match_string("repetition"))
                maximum = int(self._context.get_match_string("repetition"))

        # expression object for pattern "{(?P<min>\d)+,(?P<max>\d)+}"
        # todo: change to pattern "{(?P<min>\d+),(?P<max>\d+)}"
        elif GroupExpression((CharacterExpression(character="{"),
                              CharacterRangeExpression(start="0", end="9",
                                    name="min", max_repetitions=inf),
                              CharacterExpression(","),
                              CharacterRangeExpression(start="0", end="9",
                                    name="max", max_repetitions=inf),
                              CharacterExpression("}"))
             ).matches(self._context):
                minimum = int(self._context.get_match_string("min"))
                maximum = int(self._context.get_match_string("max"))

        if (self._context.progress < len(self._context._subject)
                and self._context.current_subject_character == "?"
                and progress != self._context.progress):
            greedy = False
            self._context.progress += 1

        return {"min_repetitions": minimum,
                "max_repetitions": maximum,
                "greedy": greedy}


def matches(pattern, string, flags=0):
    p = Parser()
    e = p.parse(pattern)
    c = EvaluationContext()
    if e.matches(string, c):
        return c.flattened_matches
    return None


class ParsingOverflowException(Exception):
    """Raised if one tries to read beyond the length of the subject."""


def _copykeys(d, k):
    """Copy key value pairs k from d into a new dict."""
    return dict(map(lambda x: (x, d[x]), k))
