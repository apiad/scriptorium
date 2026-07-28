# Balanced trees {#chap-trees}

Binary search was fast but rigid: it needs a sorted array, and keeping an array
sorted under insertions is expensive. A balanced tree keeps the logarithmic
lookups while letting us insert and delete cheaply.

## Rotations

The trick that keeps a tree balanced is the rotation — a local rearrangement of
three nodes that restores the height invariant without disturbing the sorted
order. A handful of rotation cases is enough to keep every path from the root to
a leaf within a constant factor of the ideal depth.

## Why it matters

With balance guaranteed, every operation — search, insert, delete — is
logarithmic in the worst case, not just on average. That worst-case promise is
what makes balanced trees the workhorse structure they are.
