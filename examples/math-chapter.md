---
title: Fenwick trees
stem: fenwick
---

# Same problem, half the code

The **Fenwick tree** does point-update plus range-sum in $O(\log n)$ with a
single $n$-slot array and a one-character arithmetic trick: $i \mathbin{\&} -i$,
the lowest set bit, is the entire structure encoded in one operation.

At index $i$, the cell `tree[i]` stores the sum of the array values over the
range $(i - \mathrm{lowbit}(i),\ i]$, where $\mathrm{lowbit}(i) = i \mathbin{\&} -i$.
So $\mathrm{lowbit}(6) = 2$, $\mathrm{lowbit}(8) = 8$, and $\mathrm{lowbit}(7) = 1$.

Any range sum is the difference of two prefix sums:

$$\mathrm{range\_sum}(l, r) = \mathrm{prefix}(r) - \mathrm{prefix}(l - 1)$$

The prefix walk sums the cells along a chain, stripping the lowest set bit each
step, so it takes at most $\lfloor \log_2 n \rfloor + 1$ steps:

$$\mathrm{prefix}(i) = \sum_{k \in \text{chain}(i)} \mathrm{tree}[k]$$

```python {export=fenwick_demo.py}
def lowbit(i: int) -> int:
    return i & -i
```

```{python}
from fenwick_demo import lowbit
for i in (6, 8, 7):
    print(f"lowbit({i}) = {lowbit(i)}")
```
