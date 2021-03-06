import unicodedata

def synchronize_context(fn):
    """Decorator function that wraps the Expression matching methods.

    If the wrapped expression matches, update the context to store the
    new match. If it doesn't match, call undo() on the expression to
    reset both it's internal state and the stored match in the context.

    todo: This decorator also resets the expression if the matching
    failed. Find a name for the decorator that includes this behaviour!

    """
    def __copykeys(d, k):
        """Copy key value pairs k from d into a new dict."""
        return dict(map(lambda x: (x, d[x]), k))

    def wrap_matches(obj, context):
        if fn(obj, context):
            if obj._names is not None and obj.has_current_repetition:
                context.push_match(obj._names, __copykeys(
                        obj._current_repetition, ("start", "end")))
            return True
        if len(obj._current_match):
            context.progress = obj._current_match[0]["start"]
        obj._matches.pop()
        return False

    def wrap_retry(obj, context):
        if fn(obj, context):
            if obj._names is not None and obj.has_current_repetition:
                context.override_match(obj._names, __copykeys(
                        obj._current_repetition, ("start", "end")))
            return True
        obj.undo(context)
        return False

    if fn.__name__ == "matches":
        return wrap_matches
    if fn.__name__ == "retry":
        return wrap_retry
    raise Exception("synchronize_context only works with "
                    + "Expression.matches and Expression.retry")


class EvaluationContext:
    """The evaluation context holds information about the current
    parsing state at runtime. This includes the subject, current
    parsing progress and the results of capturing expressions.
    """

    def __init__(self, subject):
        # Number of parsed characters; changed by expressions
        # during evaluation
        self._progress = 0

        # String that is being parsed
        self._subject = subject

        # Matches of capturing groups; used by BackReferenceExpressions
        # and returned as the result of successful matching operation.
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

    def push_match(self, names, value):
        for n in names:
            self._matches.setdefault(n, []).append(value)

    def override_match(self, names, value):
        for n in names:
            self._matches[n][-1] = value

    def pop_match(self, names):
        for n in names:
            self._matches[n].pop()
            if not len(self._matches[n]):
                del self._matches[n]

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
                 greedy=True, names=None):
        self._min_repetitions = min_repetitions
        self._max_repetitions = max_repetitions
        self._greedy = greedy
        self._names = tuple(names) if names is not None else None
        self._matches = []

    @property
    def _current_match(self):
        return self._matches[-1]

    @property
    def _current_repetition(self):
        return self._current_match[-1]

    @property
    def has_current_repetition(self):
        return len(self._matches) and len(self._current_match)

    @synchronize_context
    def matches(self, context):
        """Check whether the expression matches in the assigned context.

        Add every match result to self._matches for later use and update
        the context progress.
        Return True if the expression matches, else False.

        """
        self._matches.append([])
        upper_limit = (self._min_repetitions,
                       self._max_repetitions)[self._greedy]

        while (context.progress < len(context.subject)
               and len(self._current_match) < upper_limit):
            match = self._matches_once(context)
            if match is None:
                break
            self._current_match.append(match)
            context.progress = match["end"]

        return self._min_repetitions <= len(self._current_match)

    @synchronize_context
    def retry(self, context):
        """Reevaluate the expression to the next repetition count.

        This method performs a single iteration step. This includes
        updating the context progress and, if the expression is named,
        the match stored in the context.

        Note that the iteration can be performed in two directions:
        If the expression is greedy, it consumes as many characters as
        possible during the initial evaluation and we free parts of the
        subject during reevaluation.
        if the expression is nongreedy, it matches as few characters as
        possible during the initial evaluation and we consume additional
        parts of the subject during reevaluation.

        Return True if reevaluation was successful and the new
        repetition count is valid or False if the reevaluation
        failed, for example because it overflowed the repetition
        limits.

        """
        if (len(self._current_match) == (self._max_repetitions,
                                         self._min_repetitions)[self._greedy]):
            return False

        if self._greedy:
            context.progress = self._current_match.pop()["start"]
        else:
            match = self._matches_once(context)
            if match is not None:
                self._current_match.append(match)
                context.progress = match["end"]
            else:
                return False
        return True

    def undo(self, context):
        """Undo the last match with all repetitions."""
        if len(self._current_match):
            context.progress = self._current_match[0]["start"]
        if self._names is not None:
            context.pop_match(self._names)
        self._matches.pop()

    def _matches_once(self, context):
        """Evaluate the expression once without modifying state.

        Check whether the expression matches the subject inside the
        context beginning at context.progress without evaluating
        repetitions. Return None if the expression did not match, else
        a dict with keys "start" and "end" pointing to the respective
        indices in subject.

        """
        raise NotImplementedError()

    def _wrap_with_name(self, v):
        """Helper method for __str__; wrap v with name reference."""
        if self._names is None:
            return v
        for name in filter(lambda x: type(x) is str, self._names):
            return "(?P<%s>%s)" % (name, v)
        return "(%s)" % v

    def _repetition_to_string(self):
        """Helper method for __str__; build repetition string."""
        if self._min_repetitions == self._max_repetitions == 1:
            return ""
        inf = float("inf")
        if self._min_repetitions == 0 and self._max_repetitions == inf:
            r = "*"
        elif self._min_repetitions == 1 and self._max_repetitions == inf:
            r = "+"
        elif self._min_repetitions == 0 and self._max_repetitions == 1:
            r = "?"
        elif self._min_repetitions == self._max_repetitions:
            r = "{%d}" % self._min_repetitions
        else:
            r = "{%s,%s}" % ("" if self._min_repetitions == 0
                                else str(self._min_repetitions),
                             "" if self._max_repetitions == inf
                                else str(self._max_repetitions))
        if not self._greedy:
            r += "?"
        return r

    def __eq__(self, other):
        return all(map(lambda x: getattr(self, x) == getattr(other, x),
                       vars(self)))


class CharacterExpression(Expression):
    """Represents a single character."""

    def __init__(self, character, **kwargs):
        super().__init__(**kwargs)
        self._char = character

    def _matches_once(self, context):
        if context.current_subject_character == self._char:
            return {"start": context.progress, "end": context.progress + 1}
        return None

    def __str__(self):
        return self._wrap_with_name(self._char) + self._repetition_to_string()


class CharacterRangeExpression(Expression):
    """Represents a character range, like [a-z].

    For a collection of ranges, like [a-zA-Z], multiple range
    expressions are concatenated in an AnyOfOptionsExpression.

    """

    def __init__(self, start, end, **kwargs):
        super().__init__(**kwargs)
        self._start = start
        self._end = end

    def _matches_once(self, context):
        if self._start <= context.current_subject_character <= self._end:
            return {"start": context.progress, "end": context.progress + 1}
        return None

    def __str__(self):
        return (self._wrap_with_name("[%s-%s]" % (self._start, self._end))
                + self._repetition_to_string())


class AbstractIteratorExpression(Expression):
    """"""

    def __init__(self, children, **kwargs):
        super().__init__(**kwargs)
        self._children = tuple(children)

    @synchronize_context
    def matches(self, context):
        """Check whether the expression matches in the assigned context.
        """
        self._matches.append([])
        upper_limit = (self._min_repetitions,
                       self._max_repetitions)[self._greedy]

        while True:
            while len(self._current_match) < upper_limit:
                match = self._matches_once(context)
                if match is None:
                    break
                self._current_match.append(match)
            if len(self._current_match) >= self._min_repetitions:
                return True
            if not self._reevaluate_previous_repetition(context):
                return False

    @synchronize_context
    def retry(self, context):
        """Retry children before adding or removing repetitions."""
        initial_repetitions = len(self._current_match)

        if initial_repetitions == 0:
            if self._greedy:
                return False
        elif self._reevaluate_previous_repetition(context):
            return True
        if initial_repetitions == (self._max_repetitions,
                                   self._min_repetitions)[self._greedy]:
            return False

        # __retry_one_repetition returned False which means that
        # __retry_one_child was executed on each repetition, so
        # all results have been reset. Restore them up to the second
        # last repetition.
        if (self._greedy):
            for _ in range(0, initial_repetitions - 1):
                self._current_match.append(self._matches_once(context))
        else:
            for _ in range(0, initial_repetitions + 1):
                match = self._matches_once(context)
                if match is None:
                    return False
                self._current_match.append(match)
        return True


class AnyOfOptionsExpression(AbstractIteratorExpression):
    """Represents a logical-or expression with two or more values.

    This class will be instantiated for
    the following expression strings:
    * Two or more expressions concatenated with "|"
    * Character groups like "[abc]", which will be represented as an
      option group of  CharacterExpressions or CharacterRangeExpressions

    """

    def undo(self, context):
        """Undo the children that matched in each repetition."""
        for m in reversed(self._current_match):
            self._children[m["matching_child"]].undo(context)
        super().undo(context)

    def _matches_once(self, context):
        """Evaluate children in order until one matches."""
        start = context.progress
        for i, c in enumerate(self._children):
            if c.matches(context):
                return {"start": start,
                        "end": context.progress,
                        "matching_child": i}
        return None

    def _reevaluate_previous_repetition(self, context):
        """"""
        if not len(self._current_match):
            return False
        self._current_match.pop()

        current_child_index = self._current_repetition["matching_child"]
        child = self._children[current_child_index]
        start = end = context.progress

        if child.retry(context):
            if child.has_current_repetition:
                start = child._current_repetition["start"]
                end = child._current_repetition["end"]
            self._current_match.append({"start": start, "end": end})
            return True

        start_child_iteration = current_child_index + 1
        while True:
            for i in range(start_child_iteration, len(self._children)):
                child = self._children[i]
                if child.matches(context):
                    if child.has_current_repetition:
                        start = child._current_repetition["start"]
                        end = child._current_repetition["end"]
                    self._current_match.append({"start": start, "end": end})
                    return True
            start_child_iteration = 0
            if not self._reevaluate_previous_repetition(context):
                return False


class GroupExpression(AbstractIteratorExpression):
    """Represents and manages a group of expressions, like "(ab|c)". """

    def undo(self, context):
        """Undo all children, then proceed with default behaviour."""
        for _ in self._current_match:
            for c in reversed(self._children):
                c.undo(context)
        super().undo(context)

    def _matches_once(self, context):
        """Execute all child expressions in order.

        Iterate recursively over self._children to find a combination
        that suffices the match conditions of all children. This is done
        evaluating all children in order, starting with the first one.
        When a child expression can't match, the previous children are
        reevaluated.

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

        start = end = context.progress
        if __match_one_child(0):
            for c in self._children:
                if c.has_current_repetition:
                    end = c._current_repetition["end"]
            return {"start": start, "end": end}
        return None

    def _reevaluate_previous_repetition(self, context):
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
            return False
        self._current_match.pop()

        if __retry_one_child(len(self._children) - 1):
            start = end = context.progress
            for c in self._children:
                if c.has_current_repetition:
                    if c._current_repetition["start"] < start:
                        start = c._current_repetition["start"]
                    end = c._current_repetition["end"]
            self._current_match.append({"start": start, "end": end})
            return True

        while self._reevaluate_previous_repetition(context):
            result = self._matches_once(context)
            if result is not None:
                self._current_match.append(result)
                return True
        return False

    def __str__(self):
        return (self._wrap_with_name("%s")
                % "".join(map(lambda x: str(x), self._children))
                + self._repetition_to_string())


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

    def __str__(self):
        return "(?P=%s)" % self._reference + self._repetition_to_string()
