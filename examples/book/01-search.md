# Linear and binary search {#chap-search}

Searching is the foundation everything else builds on. Once data is organized
well, lookups get dramatically faster — a theme we return to in @chap-trees,
where balanced structures guarantee logarithmic access.

## The linear scan

The simplest search walks every element until it finds the target. It needs no
preparation and works on any sequence, but it costs one comparison per element,
so a miss touches the whole collection. That linear cost is the baseline every
smarter method is measured against.

## Binary search

If the sequence is sorted, we can halve the search space at every step by
comparing against the middle element. Each comparison discards half of what
remains, so the whole search finishes in a logarithmic number of steps — the
first real payoff for keeping data in order.

## Cost, more carefully

The linear scan makes at most n comparisons and the binary search at most about
log2(n), but the constants matter in practice. A linear scan over a contiguous
array is friendly to the cache and branch predictor, so for small n it can beat
a binary search that jumps around memory. The crossover point depends on element
size and hardware, but it is real: asymptotics tell you the shape of the curve,
not where two curves cross.

## When neither fits

Sometimes the data does not sit still long enough to keep it sorted, and lookups
are rare enough that paying to sort is a loss. Then a hash structure — trading
order for expected-constant lookups — is the better tool, and we take that up
when we reach hashing. The lesson that carries forward is that the right search
is a property of the whole workload, not of the query alone: how often you look,
how often the data changes, and how much order you can afford to maintain.

## A note on invariants

Every fast search rests on an invariant the structure promises to keep — sorted
order for binary search, a balance condition for trees, a good hash for tables.
The cost of a data structure is the cost of maintaining its invariant under
change, and the payoff is the speed that invariant buys at query time. Keep that
trade in view and the rest of this book reads as a catalogue of invariants and
what each one costs.
