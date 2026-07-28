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
