---
theme: book
title: Executable chapter
stem: chapter
---

# A literate, executable chapter

We define a small module and **tangle** it to a real source file with
`export=`. The same body is shown here and written to `mymath.py`.

```python {export=mymath.py}
def lowbit(i: int) -> int:
    """The lowest set bit — the whole Fenwick trick in one operation."""
    return i & -i
```

A Quarto-style `{python}` block runs in a subshell, imports the tangled module,
and shows its output as monospace — the Quarto-compatible execution mode.

```{python}
from mymath import lowbit

for i in (6, 8, 7):
    print(f"lowbit({i}) = {lowbit(i)}")
```

A native `{run}` block splices stdout as **raw markdown**, so the code can emit a
real table instead of ASCII art — the house execution model:

```python {run echo=false}
print("| n | lowbit(n) |")
print("|---|-----------|")
for i in (6, 8, 7):
    print(f"| {i} | {i & -i} |")
```
