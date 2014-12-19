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
