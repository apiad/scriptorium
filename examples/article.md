---
title: The Shape of a Good Abstraction
---

# The Shape of a Good Abstraction

::: {.lead}
An abstraction earns its keep when it hides a decision you would otherwise have to
make in a hundred places. This is an essay about how to tell the load-bearing
abstractions from the leaky ones — before you have shipped them everywhere.
:::

The word *abstraction* has been worn smooth by overuse, so let me be concrete.
An abstraction is a boundary. On one side sits a decision — a data layout, a
protocol, an ordering rule. On the other side sits everyone who would otherwise
have to know that decision to get their work done. A good boundary lets them not
know, and keeps letting them not know as the decision changes.

The leaky ones fail that second test. They hide the decision on a sunny day and
surface it the moment anything goes wrong, which is exactly when you least want a
new thing to learn. The abstraction that makes the easy case easy and the hard
case impossible has not saved you any work; it has only deferred it to the worst
possible moment.

## Hiding a decision, not a mechanism

The most common mistake is to abstract the mechanism instead of the decision. A
cache that exposes `get` and `set` has hidden a hash table, which nobody needed
hidden. A cache that guarantees a freshness bound has hidden a decision — how
stale is too stale — that every caller would otherwise have to make and re-make.
The first is a thin coat of paint; the second is a boundary worth defending.

The test is simple: name the decision the abstraction makes on your behalf. If
you cannot name one, you have wrapped a mechanism, not hidden a decision, and the
wrapper will cost more than it saves.

## The cost of the wrong seam

Every abstraction draws a seam, and the seam has a cost that shows up only under
change. Put the seam in the wrong place and small changes tear across it —
touching both sides at once — which is the observable symptom of a leak. Put it
in the right place and the same changes stay on one side.

So the question to ask, before writing the interface, is not "what operations do
I need" but "what will change independently." The seam belongs between the things
that move at different rates. Get that right and the interface almost writes
itself; get it wrong and no amount of interface polish will save you.

## When not to

Not every decision deserves a boundary. A boundary you cross constantly, that
never changes, and that everyone already understands is pure overhead — a toll
booth on a road with no traffic. Abstraction is a bet that a decision will change
or spread; when you are confident it will do neither, the honest move is to
inline it and move on.
