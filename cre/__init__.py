"""cre - custom regular expressions

This module provides a custom regex implementation I wrote to get a
better understanding of regular expressions. It aims to support the
full feature set of pythons builtin re module. It is not optimized
for speed and should not be used in production code.
If you want to see how the module works, read the docstrings of the
Expression and Parser classes.

- Philipp Schiffmann

"""

from .expression import *
from .parser import *


# This object is used by the module function cre.compile(), which in
# turn is used by cre.match(), cre.search() and others.
default_parser = Parser()


class RegexObject:
    """Compiled regular expression objects"""

    def __init__(self, expression_tree, pattern, groups, groupindex, flags=0):
        self._expression_tree = expression_tree
        self.pattern = pattern
        self.flags = flags
        self.groups = groups
        self.groupindex = groupindex

    def match(self, string, pos=None, endpos=None):
        """match(string[, pos[, endpos]]) -> match object or None.
        Matches zero or more characters at the beginning of the string"""
        m = MatchObject(self, string[pos:endpos])
        if self._expression_tree.matches(m):
            return m


class MatchObject:
    """The result of re.match() and re.search().
    Match objects always have a boolean value of True.

    It is used as a "context" by Expression objects during matching. It
    can be queried for the string, the current consumed and free
    characters and the results of capturing expressions.

    """

    def __init__(self, re, string, pos, endpos):
        self.re = re
        self.pos = pos
        self.endpos = endpos
        self.string = string

        # Matches of capturing groups; used by BackReferenceExpressions
        # and returned as the result of successful matching operation.
        self._matches = [[]] * (re.groups + 1)

        # Number of consumed characters; changed by expressions
        # during evaluation
        self._progress = 0

    @property
    def lastindex(self):
        raise NotImplementedError()

    @property
    def lastgroup(self):
        raise NotImplementedError()

    @property
    def _remaining_string_length(self):
        return len(self.string) - self._progress

    @property
    def _current_character(self):
        return self.string[self._progress]

    #'lastgroup', 'lastindex', regs', 'span',

    def expand(self):
        """expand(template) -> str.

        Return the string obtained by doing backslash substitution
        on the string template, as done by the sub() method.

        """
        raise NotImplementedError()

    def group(self, *groups):
        """group([group1, ...]) -> str or tuple.
        Return subgroup(s) of the match by indices or names.
        For 0 returns the entire match."""
        if len(groups) == 0:
            return self._matches[0]
        try:
            if len(groups) == 1:
                return self._matches[groups[0]]
            return tuple(map(lambda x: self._matches[x], groups))
        except KeyError:
            raise IndexError("no such group")

    def groups(self, default=None):
        """groups([default=None]) -> tuple.
        Return a tuple containing all the subgroups of the match, from 1.
        The default argument is used for groups
        that did not participate in the match"""
        return tuple(map(lambda x: x[1] if x[1] is not None else default,
                         filter(lambda k, _: type(k) is int,
                                self._matches.items())))

    def groupdict(self):
        """groupdict([default=None]) -> dict.
        Return a dictionary containing all the named subgroups of the match,
        keyed by the subgroup name. The default argument is used for groups
        that did not participate in the match"""

    def start(self, group=0):
        """start([group=0]) -> int.

        Return index of the end of the substring matched by group.

        """
        if group in self._matches and group not in self._spans:
            return -1
        try:
            return self._spans[group]["start"]
        except KeyError:
            raise IndexError("no such group")

    def end(self, group=0):
        """end([group=0]) -> int.
        Return index of the end of the substring matched by group."""
        if group in self._matches and group not in self._spans:
            return -1
        try:
            return self._spans[group]["end"]
        except KeyError:
            raise IndexError("no such group")

    def __bool__(self):
        """Match objects always have a boolean value of True.
        Since match() and search() return None when there is no match,
        you can test whether there was a match with a simple if
        statement."""
        return True

    def __repr__(self):
        """return repr(self)."""
        return ("<cre.MatchObject object; span=({0}, {1}), match='{2}'>"
                .format(self._spans[0]["start"],
                        self._spans[0]["end"],
                        self._matches[0]))

    __str__ = __repr__
    """return str(self)."""


def compile(pattern, flags=0):
    """Compile a regular expression pattern, returning a pattern object."""
    return default_parser.compile(pattern, flags)

def match(pattern, string, flags=0):
    """Try to apply the pattern at the start of the string, returning
    a match object, or None if no match was found."""
    return compile(pattern, flags).match(string)
