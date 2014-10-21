#!/usr/local/bin/python3

"""
cre - custom regular expressions

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
        return self._subject[self._progress:]

    @property
    def current_subject_character(self):
        return self._subject[self._progress]

    @property
    def matches(self):
        return self._matches

    @matches.setter
    def matches(self, value):
        self._matches = value

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
        self._results = []

    def matches(self, context):
        """Check whether the expression matches in the assigned context.

        Internally, dispatch the call depending on whether the
        expression is greedy. If the expression matches and has a name,
        update the context to store the last match.
        Return True if the expression matches, else False.

        """
        matches = (self._matches_greedy(context) if self._greedy
                   else self._matches_minimal(context))
        if matches and self._name != None:
            context.matches.setdefault(self._name, []) \
            .append(self._results[-1][-1])
        return matches

    def retry(self, context):
        """Iterate the next repetition count."""
        matches = (self._retry_greedy(context) if self._greedy
                   else self._retry_minimal(context))
        if self._name != None:
            if matches:
                context.matches[self._name][-1] = self._results[-1][-1]
            else:
                context.matches[self._name].pop()
                if len(context.matches[self._name]) == 0:
                    del context.matches[self._name]
        return matches

    def _matches_greedy(self, context):
        """Call _matches_once up to _max_repetitions times.

        Increase the context progress for each match.

        The match will fail if _matches_once matches less often than
        _min_repetitions times or if the remaining subject length is
        zero.
        If the match does not fail, add every match result to
        self._results and return True. Else discard the results and
        return False.

        """
        progress = context.progress
        matches = []
        while (context.progress < len(context.subject)
               and len(matches) < self._max_repetitions):
            match = self._matches_once(context)
            if match is None:
                break
            matches.append(match)
            context.progress = match["end"]

        if len(matches) < self._min_repetitions:
            context.progress = progress
            return False
        self._results.append(matches)
        return True

    def _matches_minimal(self, context):
        """Call _matches_once up to _min_repetitions times."""
        progress = context.progress
        matches = []
        while (context.progress < len(context.subject)
               and len(matches) < self._min_repetitions):
            match = self._matches_once(context)
            if match is None:
                break
            matches.append(match)
            context.progress = match["end"]
        if len(matches) < self._min_repetitions:
            context.progress = progress
            return False
        self._results.append(matches)
        return True

    def _retry_greedy(self, context):
        """If this expression has a range of valid repetitions and the current
        repetition count is higher than the minimum repetition count, free the
        last consumed match and return True, else False.
        """
        if len(self._results[-1]) <= self._min_repetitions:
            self._results.pop()
            return False
        m = self._results[-1].pop()
        context.progress -= m["end"] - m["start"]
        return True

    def _retry_minimal(self, context):
        """"""
        if len(self._results[-1]) == self._max_repetitions:
            self._results.pop()
            return False
        m = self._matches_once(context)
        if match is None:
            return False
        self._results[-1].append(m)
        subject.progress += m["end"] - m["start"]

    def _matches_once(self, context):
        """Check whether the expression matches the subject inside the
        context beginning at context.progress without evaluating
        repetitions. Return None if the expression did not match, else a
        dict with keys "start" and "end" pointing to the respective
        indices in subject."""
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
    """Represents a character range, like [a-z]. For a collection of ranges,
    like [a-zA-Z], multiple range expressions are concatenated in a
    GroupExpression."""

    def __init__(self, start, end, **kwargs):
        super().__init__(**kwargs)
        self._start = start
        self._end = end

    def _matches_once(context):
        if self._start <= context.current_subject_character <= self._end:
            context.progress += 1
            return {"start": context.progress - 1, "end": context.progress}
        return None


class AnyOfOptionsExpression(Expression):
    """Represents a logical-or expression with two or more values.

    This class will be instantiated for the following expression strings:
    * Two expressions concatenated with "|"
    * Character groups like \w

    The latter case will contain 16 options, because each value in the range
    will be its own CharacterExpression instance.

    """

    def __init__(self, options, **kwargs):
        super().__init__(**kwargs)
        self._options = options

    def _matches_once(self, context):
        """Evaluate each option in order until the first one matches."""
        start = context.progress
        for o in self._options:
            if o.matches(context):
                return {"start": start, "end": context.progress + 1}
        return None


class GroupExpression(Expression):
    """Represents a group of expressions."""

    def __init__(self, children, **kwargs):
        super().__init__(**kwargs)
        self._children = children

    def _matches_once(self, context):
        start = context.progress
        # Handle the first expression in the group seperately because there is
        # no previous expression that could be retried if the initial match
        # fails.
        if not self._children[0].matches(context):
            return None
        for i in range(1, len(self._children) + 1):
            current = self._children[i]
            previous = self._children[i - 1]
            can_retry = True
            while can_retry:
                if current.matches(context):
                    continue
                can_retry = previous.retry(context)
            # We only arrive here if the current expression didn't match with
            # any of the previous repetitions.
            return None
        return {"start": start, "end": context.progress + 1}


class BackReferenceExpression(Expression):
    """"""


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
        self.current = {"state": "unknown"}

        while self._context.progress < len(pattern):
            getattr(self, "_parse_" + self._current["state"])()

        if len(self._stack) > 1:
            raise Exception("More expressions opened than closed")
        root = GroupExpression(self._groups.pop()["children"])
        self._context = None
        return root

    def _parse_unkown(self):
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
            self._current = {
                    "state": "character",
                    "character": self._context.current_subject_character}
        self._context.progress += 1

    def _parse_character(self):
        """Handle parsing when a simple character expression was detected."""
        args = {"character": self._current["character"]}
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
        """Read repetitions and greedy behaviour from the current position.

        Return a dict with keys greedy, min_repetitions and max_repetitions,
        like the named parameters for Expression, filled with resolved or
        default values.

        todo: handle repetitions indications like {1,} or {5}

        """
        minimum, maximum, greedy = 1, 1, True
        inf = float("inf")
        if self._context.current_subject_character == "+":
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
        else:
            # expression object for pattern "{\d+,\d+}"
            if GroupExpression((CharacterExpression(character="{"),
                                CharacterRangeExpression(start="0", end="9",
                                    name="min", max_repetitions=inf),
                                CharacterExpression(","),
                                CharacterRangeExpression(start="0", end="9",
                                    name="max", max_repetitions=inf),
                                CharacterExpression("}"))
            ).matches():
                minimum = int(self._context.get_match_string("min"))
                maximum = int(self._context.get_match_string("max"))

        if minimum is not None and self._context.current_subject_character == "?":
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

def main():
    print("main")

if __name__ == "__main__":
    main()
