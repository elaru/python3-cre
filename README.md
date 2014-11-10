custom regular expressions
==========================

Overview
--------

cre is a regular expression interpreter written in Python3. I am writing this
package to get a better understanding of regular expressions. I intend to
develop a feature complete implementation that yields identical results as the
[official implementation](https://docs.python.org/3.4/library/re.html).

However, this implementation is written for personal training only and is not
optimized for performance or guaranteed to work as expected! I hope you find
the documentation and code helpful if you want to understand how regular
expressions are evaluated, but I recommend to **not use it in production source
code**.


Usage
-----

Yet to come.


Architecture
------------

This paragraph explains the internal software architecture. It is not relevant
to understand the behaviour of this module.

**TL;DR**:
`Expression` as GoF interpreter, `Parser` as state machine.


### Expressions as classes

All expressions are represented by subclasses of `Expression`. For example,
if we parse the pattern `a(bc)+`, the leading `a` will be instantiated as a
`CharacterExpression`, while `(bc)+` will be turned into a `GroupExpression`
consisting of another two CharacterExpressions. This way, a regex pattern is
represented by a nested expression object tree at runtime. The evaluation is
handled recursively by the expression classes according to the GoF interpreter
pattern.

All expressions share a couple of qualities that are implemented in the base
class. All expressions have

* lower and upper repetition limits: `?`, `*`, `+`, `{m}`, `{m,n}`
* a greedy / nongreedy indicator: `+`, `+?`, ...
* optinally a name: `(P<name>foo)`

You can pass values for any of these attributes to the `Expression`
constructor. Subclasses will usually add their own parameters: for example,
the `CharacterExpression` also expects the character it should match.

The matching behaviour is implemented in `_matches_once()`, which subclasses
must implement. It returns a single match result without handling repetitions,
like `{"start": 0, "end": 1}`, or `None` if the expression didn't match. This
method is in return called by `matches()` and `retry()` - you can probably
imagine the responsibility of those.

`matches()` performs the initial match of an expression using `_matches_once()`
until it reaches the appropriate repetition limit. For greedy expressions this
is the upper limit, while nongreedy expressions only iterate until they reach
their lower limit. The method returns a boolean indicating the success or
failure of the match operation.

Likewise, `retry()` reevaluates the expression. In case of greedy expressions
this is accomplished by freeing the last repetition. Nongreedy expressions try
to allocate additional parts of the subject by calling `_matches_once()` again.


### Generating expression objects from a string pattern

A paragraph or two about the `Parser` class...


Examples
--------

To understand the difficulties you encounter when parsing a string with regex,
consider the work that has to be done by the algorithm:

Each expression matches a certain set of characters, and the expressions have
to match in a certain order. Parts of the subject are assigned to the
individual expressions during evaluation. That being said, our algorithm has to
distribute parts of the subject in a way that every subject character is
consumed exactly once.

Therefore, every expression will initially consume as many characters of the
subject as possible (or as few, if the expression is nongreedy). Then, if a
later expression can't match the subject anymore, all previous matches have to
be rollbacked and reevaluated with fewer (or more) repetitions to find a valid
distribution.

The following section describes various use cases one has to consider when
evaluating regular expressions. The examples are ordered by complexity. Look
at the third example for an illustration.


### Reevaluating a single previous expression #1
```
subject := aa
pattern := ^a+a$
```

### Reevaluating a single previous expression #2
```
subject := ab
pattern := a*?b
```

### Reevaluating multiple previous expressions
```
subject := aaaaaa
pattern := a{3,}a{2,}a
```
*Illustration of the reevaluation procedure*
```
step |  a{3,}  |  a{2,}  |  a
 #1     1 - 6       -       -
 #2     1 - 5       -       -
 #3     1 - 4       -       -
 #4     1 - 4     5 - 6     -
 #5     1 - 3       -       -
 #6     1 - 3     4 - 5     -
 #7     1 - 3     4 - 4     6
```

### Reevaluating previous group repetitions
```
subject := aaaaaaaaaaaaa
pattern := (a+a{2,}a){3,}a
```
