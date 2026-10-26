"""display() and rich last expressions in python blocks, and the bundles they print."""

from scriptorium.execute import ExecEnv

RICH = '''
class R:
    def _repr_mimebundle_(self, include=None, exclude=None):
        return {"text/markdown": "**rich**", "text/plain": "R()"}, {"caption": "c"}
'''


def bundles(stdout):
    from scriptorium.bundles import split
    return [b for b in split(stdout) if isinstance(b, dict)]


def test_display_prints_a_bundle(tmp_path):
    res = ExecEnv(cwd=str(tmp_path)).run(RICH + "display(R())\n", "python")
    [b] = bundles(res.stdout)
    assert b["data"]["text/markdown"] == "**rich**" and b["metadata"] == {"caption": "c"}


def test_display_metadata_argument_wins(tmp_path):
    res = ExecEnv(cwd=str(tmp_path)).run(RICH + "display(R(), metadata={'caption': 'd'})\n", "python")
    assert bundles(res.stdout)[0]["metadata"]["caption"] == "d"


def test_rich_last_expression_is_displayed(tmp_path):
    res = ExecEnv(cwd=str(tmp_path)).run(RICH + "R()\n", "python")
    assert len(bundles(res.stdout)) == 1


def test_plain_last_expression_prints_nothing(tmp_path):
    assert ExecEnv(cwd=str(tmp_path)).run("1 + 1\n", "python").stdout == ""


def test_single_repr_methods_are_enough(tmp_path):
    src = "class S:\n    def _repr_svg_(self): return '<svg/>'\nS()\n"
    assert bundles(ExecEnv(cwd=str(tmp_path)).run(src, "python").stdout)[0]["data"] == {"image/svg+xml": "<svg/>"}


def test_traceback_still_numbers_cell_lines(tmp_path):
    res = ExecEnv(cwd=str(tmp_path)).run("x = 1\nraise ValueError('boom')\n", "python")
    assert res.failed and 'File "<cell>", line 2' in res.stdout + res.stderr
