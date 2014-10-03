#!/usr/local/bin/python3


class Parser:
    def __init__(self):
        self._progress = 0
        self._groups = []

    def parse(self, pattern):
        if len(self._groups):
            raise Exception("Parser already in use!")
        root = GroupExpression()
        self._initialize_group_pattern()
        
        while self._progress < len(pattern):
            if char == self._current_group["closing_tag"]:
                pass
            else:
                e = CharacterExpression(char)
                self._current_group["children"].append(e)

        root = GroupExpression(self._groups.pop()["children"])
        return root

    def _initialize_group_pattern(self):
        self._current = {
            "": ""
        }


class EvaluationContext:
    """The evaluation context holds information about the current parsing state
    during at runtime. This includes the current parsing progress and the
    results of capturing expressions."""

    def __init__(self, subject):
        self._progress = 0
        self._subject = subject
        self._matches = {}

    @property
    def subject(self):
        return subject

    @property
    def remaining_subject(self):
        return self._subject[self._progress:]

    @property
    def current_subject_character(self):
        return self._subject[self._progress]


class Expression:
    """Base class for all expressions."""

    def __init__(self, **kwargs):
        self._min_repetitions = kwargs.getdefault("min_repetitions", 1)
        self._max_repetitions = kwargs.getdefault("max_repetitions", 1)
        self._greedy = kwargs.getdefault("greedy", True)
        self._matches = []

    def matches(self, subject, context):
        """Check whether the expression matches the assigned subject beginning
        at context.progress. If True, update the context progress.
        """
        if self._greedy:
            return self._matches_greedy(subject, context)
        return self._matches_minimal(subject, context)

    def retry(self, subject, context):
        """Iterate the next repetition count."""
        if self._greedy:
            return self._retry_greedy(subject, context)
        return self._retry_minimal(subject, context)

    def _matches_greedy(self, subject, context):
        """Call _matches_once up to _max_repetitions times."""
        matches = []
        while len(matches) < self._max_repetitions:
            match = self._matches_once(subject, context)
            if match is None:
                break
            matches.append(match)
            if match["end"] >= len(subject):
                break
        if len(matches) >= self._min_repetitions:
            self._matches.append(matches)
            return True
        return False

    def _matches_minimal(self, subject, context):
        """Call _matches_once up to _min_repetitions times."""
        matches = []
        while len(matches) < self._min_repetitions:
            match = self._matches_once(subject, context)
            if match is None:
                break
            matches.append(match)
            if match["end"] >= len(subject):
                break
        if len(matches) >= self._min_repetitions:
            self._matches.append(matches)
            return True
        return False

    def _retry_greedy(self, subject, context):
        """If this expression has a range of valid repetitions and the current
        repetition count is higher than the minimum repetition count, free the
        last consumed match and return True, else False.
        """
        if len(self._matches[-1]) <= self._min_repetitions:
            self._matches.pop()
            return False
        m = self._matches[-1].pop()
        context.progress -= m["end"] - m["start"]
        return True

    def _retry_minimal(self, subject, context):
        raise NotImplementedError()

    def _matches_once(self, subject, context):
        """Check whether the assigned subject matches the expression beginning
        at context.progress without evaluating repetitions. Return None if the
        expression did not match, else a dict with keys "start" and "end"
        pointing to the respective indices in subject."""
        raise NotImplementedError()


class CharacterExpression(Expression):
    """Represents a single character."""

    def __init__(self, char, **kwargs):
        super(**kwargs)
        self._char = char

    def _matches_once(self, subject, context):
        if subject[context.progress] == self._char:
            context.progress += 1
            return {"start": context.progress - 1, "end": context.progress}
        return None


class CharacterRangeExpression(Expression):
    """Represents a character range, like [a-z]. For a collection of ranges,
    like [a-zA-Z], multiple range expressions are concatenated in a
    GroupExpression."""

    def __init__(self, start, end, **kwargs):
        super(**kwargs)
        self._start = start
        self._end = end

    def _matches_once(subject, context):
        if self._start <= subject[context.progress] <= self._end:
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

    def __init__(self, options):
        super()
        self._options = options

    def _matches_once(self, subject, context):
        """Evaluate each option in order until the first one matches."""
        start = context.progress
        for o in self._options:
            if o.matches(subject, context):
                return {"start": start, "end": context.progress + 1}
        return None


class CapturingExpression(Expression):
    """"""
    def __init__(self, name, wrap, **kwargs):
        super(**kwargs)
        self._name = name
        self._wrap = wrap

    def matches(self, subject, context):
        match = self._wrap.matches(subject, context)
        return match


class GroupExpression(Expression):
    """Represents a group of expressions."""

    def __init__(self, children):
        super()
        self._children = children

    def _matches_once(self, subject, context):
        start = context.progress
        # Handle the first expression in the group seperately because there is
        # no previous expression that could be retried if the initial match
        # fails.
        if not self._children[0].matches(subject, context):
            return None
        for i in range(1, len(self._children) + 1):
            current = self._children[i]
            previous = self._children[i - 1]
            can_retry = True
            while can_retry:
                if current.matches(subject, context):
                    continue
                can_retry = previous.retry(subject, context)
            # We only arrive here if the current expression didn't match with
            # any of the previous repetitions.
            return None
        return {"start": start, "end": context.progress + 1}


class BackReferenceExpression(Expression):
    """"""


def main():
    print("main")

if __name__ == "__main__":
    main()
