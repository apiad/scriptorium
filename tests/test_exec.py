"""VS3 acceptance: fence directives, tangle, and subshell execution + splice."""

from scriptorium.execute import ExecEnv, RunResult
from scriptorium.freeze import Freeze
from scriptorium.fence import parse_fence
from scriptorium.parse import parse
from scriptorium.tangle import collect
from scriptorium.tangle import test as tangle_test
from scriptorium.tangle import write as tangle_write


def _outputs(units):
    return [u.html for u in units if u.name == "output"]


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


def test_blocks_are_independent_by_default(tmp_path):
    env = ExecEnv(cwd=str(tmp_path))
    units = parse('```{python}\nx = 1\n```\n\n```{python}\nprint(x)\n```', env=env)
    assert "NameError" in "".join(_outputs(units))


def test_continue_chains_blocks(tmp_path):
    env = ExecEnv(cwd=str(tmp_path))
    units = parse('```{python}\na = 1\nprint("first")\n```\n\n'
                  '```{python continue}\nb = a + 1\n```\n\n'
                  '```{python continue}\nprint(a + b)\n```', env=env)
    outs = _outputs(units)
    assert len(outs) == 2
    assert "3" in outs[1] and "first" not in outs[1]


def test_continue_after_failure_resumes_prior_state(tmp_path):
    env = ExecEnv(cwd=str(tmp_path))
    units = parse('```{python}\nx = 1\nprint("one")\n```\n\n'
                  '```{python continue}\nx = 99\nint("3.5")\n```\n\n'
                  '```{python continue}\nprint(x + 1)\n```', env=env)
    outs = _outputs(units)
    assert len(outs) == 3
    assert "ValueError" in outs[1]
    assert "2" in outs[2] and "Traceback" not in outs[2] and "one" not in outs[2]


def test_continue_without_predecessor_warns(tmp_path):
    env = ExecEnv(cwd=str(tmp_path))
    units = parse('```{python continue}\nprint(41 + 1)\n```', env=env)
    assert "42" in "".join(_outputs(units))
    assert len(env.warnings) == 1 and "print(41 + 1)" in env.warnings[0]


def test_continue_does_not_cross_newpage(tmp_path):
    env = ExecEnv(cwd=str(tmp_path))
    units = parse('```{python}\nx = 1\n```\n\n\\newpage\n\n'
                  '```{python continue}\nprint(x)\n```', env=env)
    assert "NameError" in "".join(_outputs(units))
    assert len(env.warnings) == 1


def test_python_traceback_is_cell_relative(tmp_path):
    r = ExecEnv(cwd=str(tmp_path)).run('x = 1\nint("3.5")', "python")
    assert r.failed
    assert 'File "<cell>", line 2' in r.stderr
    assert 'int("3.5")' in r.stderr and "^" in r.stderr
    assert "<stdin>" not in r.stderr and "_scriptorium_driver" not in r.stderr


def test_syntax_error_reports_cell_line(tmp_path):
    r = ExecEnv(cwd=str(tmp_path)).run("x = 1\ny = (2,\n", "python")
    assert r.failed and "SyntaxError" in r.stderr
    assert 'File "<cell>", line 2' in r.stderr


def test_sys_exit_zero_is_success(tmp_path):
    env = ExecEnv(cwd=str(tmp_path))
    ok = env.run('import sys\nprint("a")\nsys.exit(0)', "python")
    assert ok == RunResult("a\n", "", False)
    assert env.run("import sys\nsys.exit(3)", "python").failed


def test_freeze_roundtrips_failure(tmp_path):
    src = 'raise ValueError("boom")'
    r1 = ExecEnv(cwd=str(tmp_path), freeze=Freeze(tmp_path / "f.json")).run(src, "python")
    r2 = ExecEnv(cwd=str(tmp_path), freeze=Freeze(tmp_path / "f.json")).run(src, "python")
    assert r1.failed and "boom" in r1.stderr
    assert r2 == r1


def test_freeze_legacy_string_entry_reads_as_success(tmp_path):
    fz = Freeze(tmp_path / "f.json")
    fz.get = lambda key: "legacy\n"
    r = ExecEnv(cwd=str(tmp_path), freeze=fz).run("print(1)", "python")
    assert r == RunResult("legacy\n", "", False)


def test_parse_fence_continue_flag():
    assert parse_fence("{python continue}").cont is True
    assert parse_fence("python {run continue}").cont is True
    assert parse_fence("{python}").cont is False
