from .expression import *

class Parser:
    """The parser creates expression object trees from pattern strings.
    """

    def __init__(self):
        self._context = None
        self._stack = []
        self._group_count = 1
        self._groupindex = {}
        self._expression_cache = {}

    @property
    def _current_state(self):
        return self._stack[-1]["state"]

    @property
    def _current_children(self):
        return self._stack[-1]["children"]

    @property
    def _current(self):
        return self._stack[-1]

    def parse(self, pattern):
        self._context = EvaluationContext(pattern)
        self._group_count = 1
        self._stack.append({"state": "root", "children": []})

        while self._context.progress < len(pattern):
            getattr(self, "_parse_" + self._current_state)()

        if len(self._stack) > 1:
            raise Exception("More expressions opened than closed")

        root = GroupExpression(self._stack.pop()["children"], names=(0,))
        self._context = None
        return root

    def _parse_root(self):
        """Push unknown state on the stack to keep parsing running."""
        self._stack.append({"state": "unknown"})

    def _parse_unknown(self):
        """Find the appropriate parse_* method for the next character."""
        self._stack.pop()
        char = self._context.current_subject_character
        new_state = {"\\": {"state": "escaped"},
                     "(" : {"state": "conjunction",
                            "children": [],
                            "first_time_parsing": True},
                     "[" : {"state": "character_group",
                            "children": []}
                    }.get(char, None)
        if new_state is not None:
            self._context.progress += 1
            self._stack.append(new_state)

        elif char in ("]", ")"):
            raise Exception("The character '%s' at position %s closes "
                            + "a group which was never opened."
                            % (char, self._context.progress))

        elif char == "|":
            if not len(self._current_children):
                raise Exception("The character '|' at position %s creates a "
                                + "disjunction, but the left expression is "
                                + "missing." % self._context.progress)
            self._context.progress += 1
            self._stack.append({"state": "disjunction",
                                "children": [self._current_children.pop()]})
            self._stack.append({"state": "unknown"})

        else:
            self._stack.append({"state": "character"})

    def _parse_character(self):
        """Parse the next character as CharacterExpression."""
        args = {"character": self._context.current_subject_character}
        self._context.progress += 1
        args.update(self._resolve_repetitions())
        self._stack.pop()
        self._current_children.append(CharacterExpression(**args))

    def _parse_character_group(self):
        pass

    def _parse_conjunction(self):
        """Extend or close the current GroupExpression."""
        if self._current["first_time_parsing"]:
            self._current["first_time_parsing"] = False
            self._current["names"] = [self._group_count]
            self._group_count += 1
            if GroupExpression(children=(
                    CharacterExpression("?"),
                    CharacterExpression("P"),
                    CharacterExpression("<"),
                    GroupExpression(children=(
                        CharacterRangeExpression(start="a", end="z",
                                                 max_repetitions=float("inf")),
                    ), names=("name",)),
                    CharacterExpression(">")
                )).matches(self._context):
                # Search for the pattern "?P<(?P<name>[a-z]+)>" with this
                # expression object right after the opening parenthesis
                #
                # todo: Replace "[a-z]" with "\w" once the
                #       AnyOfOptionsExpression works.
                self._current["names"].append(
                    self._context.get_match_string("name"))

        if self._context.current_subject_character == ")":
            if not len(self._current_children):
                raise Exception("The assigned pattern contains an empty group"
                                + "at position %s." % self._context.progress)
            self._context.progress += 1
            args = {"children": self._current_children,
                    "names": self._current["names"]}
            args.update(self._resolve_repetitions())
            self._stack.pop()
            self._current_children.append(GroupExpression(**args))

        else:
            self._stack.append({"state": "unknown"})


    def _parse_disjunction(self):
        """Parse the contents of a character group."""

    def _parse_escaped(self):
        """Parse either a as special sequence or as escaped character.

        This method will either create an appropriate expression for
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
                                    names=("repetition",)),
                    CharacterExpression("}"))
             ).matches(self._context):
                minimum = maximum = int(
                    self._context.get_match_string("repetition"))

        # expression object for pattern "{(?P<min>\d*),(?P<max>\d*)}"
        elif GroupExpression((CharacterExpression(character="{"),
                              GroupExpression(
                                    (CharacterRangeExpression(start="0",
                                        end="9", min_repetitions=0,
                                        max_repetitions=inf),),
                                    names=("min",)),
                              CharacterExpression(","),
                              GroupExpression(
                                    (CharacterRangeExpression(start="0",
                                        end="9", min_repetitions=0,
                                        max_repetitions=inf),),
                                    names=("max",)),
                              CharacterExpression("}"))
             ).matches(self._context):
                minimum = self._context.get_match_string("min")
                maximum = self._context.get_match_string("max")
                minimum = int(minimum) if len(minimum) else 0
                maximum = int(maximum) if len(maximum) else inf

        if (self._context.progress < len(self._context._subject)
                and self._context.current_subject_character == "?"):
            greedy = False
            self._context.progress += 1

        return {"min_repetitions": minimum,
                "max_repetitions": maximum,
                "greedy": greedy}
