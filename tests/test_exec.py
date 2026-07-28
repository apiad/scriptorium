"""VS3 acceptance: fence directives, tangle, and subshell execution + splice."""

from scriptorium.execute import ExecEnv
from scriptorium.fence import parse_fence
from scriptorium.parse import parse
from scriptorium.tangle import collect
from scriptorium.tangle import test as tangle_test
from scriptorium.tangle import write as tangle_write


def test_parse_fence_forms():
    assert parse_fence("{python}").run and parse_fence("{python}").output_mode == "code"
    native = parse_fence("python {run}")
    assert native.run and native.output_mode == "asis"
    assert parse_fence("python {export=a/b.py}").export == "a/b.py"
    assert parse_fence("python").run is False
    assert parse_fence("python {run echo=false}").echo is False
    assert parse_fence("python {name=frag}").name == "frag"


def test_tangle_concatenates_and_is_idempotent(tmp_path):
    src = "```python {export=m.py}\na = 1\n```\n\ntext\n\n```python {export=m.py}\nb = 2\n```"
    assert collect(src) == {"m.py": "a = 1\nb = 2\n"}  # single-newline join (illiterate-compatible)
    tangle_write(src, tmp_path)
    assert (tmp_path / "m.py").read_text() == "a = 1\nb = 2\n"
    assert tangle_test(src, tmp_path) == []


def test_native_run_splices_markdown(tmp_path):
    env = ExecEnv(cwd=str(tmp_path))
    units = parse('```python {run echo=false}\nprint("**hi**")\n```', env=env)
    html = "".join(u.html for u in units)
    assert "<strong>hi</strong>" in html  # stdout re-parsed as markdown


def test_quarto_block_shows_source_and_monospace_output(tmp_path):
    env = ExecEnv(cwd=str(tmp_path))
    units = parse('```{python}\nprint("x=1")\n```', env=env)
    assert any(u.name == "code" for u in units)  # source shown
    assert any(u.name == "output" and "x=1" in u.html for u in units)


def test_no_env_means_no_execution():
    units = parse('```{python}\nprint("nope")\n```')  # no ExecEnv
    assert all(u.name != "output" for u in units)


def test_freeze_cache_avoids_rerun(tmp_path):
    from scriptorium.freeze import Freeze

    fz = Freeze(tmp_path / "f.json")
    env = ExecEnv(cwd=str(tmp_path), freeze=fz)
    out1 = env.run("import random; print(random.random())", "python")
    env.reset_session()  # same program again (no accumulated prior cell)
    out2 = env.run("import random; print(random.random())", "python")
    assert out1 == out2  # second call served from cache, not re-run


def test_tangle_is_byte_exact_across_interleaved_blocks():
    # export blocks targeting one file, interleaved with prose, concatenate with a
    # single newline into byte-exact source (the illiterate-compatible contract).
    src = (
        "```python {export=m.py}\nclass A:\n    def __init__(self):\n        self.x = 1\n```\n\n"
        "Some prose between the blocks.\n\n"
        "```python {export=m.py}\n    def inc(self):\n        self.x += 1\n```"
    )
    assert collect(src)["m.py"] == (
        "class A:\n    def __init__(self):\n        self.x = 1\n"
        "    def inc(self):\n        self.x += 1\n"
    )


def test_export_provenance_line_ranges():
    # two blocks tangling to the same file get consecutive line-range labels
    src = ("```python {export=m.py}\na = 1\nb = 2\n```\n\nprose\n\n"
           "```python {export=m.py}\nc = 3\n```")
    units = parse(src)
    labels = [u.html for u in units if "code-file" in u.html]
    assert "m.py · L1–2" in labels[0]   # first block occupies lines 1-2
    assert "m.py · L3–3" in labels[1]   # second block continues at line 3


def test_session_state_shared_across_blocks(tmp_path):
    env = ExecEnv(cwd=str(tmp_path))
    units = parse('```{python}\ndef greet(): return "hi"\n```\n\n'
                  '```{python}\nprint(greet())\n```', env=env)
    out = "".join(u.html for u in units if u.name == "output")
    assert "hi" in out and out.count("hi") == 1  # shared state, no duplicated output


def test_session_resets_on_newpage(tmp_path):
    env = ExecEnv(cwd=str(tmp_path))
    units = parse('```{python}\nx = 1\n```\n\n\\newpage\n\n```{python}\nprint(x)\n```', env=env)
    out = "".join(u.html for u in units if u.name == "output")
    assert "NameError" in out  # x is gone after the chapter boundary
