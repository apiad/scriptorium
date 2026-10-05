"""scriptorium CLI: `render` (weave to PDF or HTML) and `tangle` (extract source)."""

import argparse
import sys
from pathlib import Path

from .tangle import test as tangle_test
from .tangle import write as tangle_write


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="scriptorium")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render", help="render a Markdown file to PDF or HTML")
    r.add_argument("input", type=Path)
    r.add_argument("-o", "--output", type=Path, default=None)
    r.add_argument("--no-execute", action="store_true", help="do not run code blocks")
    r.add_argument("--theme", default=None,
                   help="override the document's frontmatter `theme:`")
    r.add_argument("--html", action="store_true",
                   help="write the HTML document instead of a PDF (needs no WeasyPrint)")

    t = sub.add_parser("tangle", help="extract export= code blocks to source files")
    t.add_argument("input", type=Path)
    t.add_argument("-d", "--dir", type=Path, default=Path("."))
    t.add_argument("--test", action="store_true", help="check idempotency, write nothing")

    args = p.parse_args(argv)
    src = args.input.read_text(encoding="utf-8")
    stem = args.input.stem

    if args.cmd == "render" and args.html:
        from .render import render_html

        cwd = str(args.input.resolve().parent)
        if args.input.suffix in (".yaml", ".yml"):  # a project
            from .project import load as load_project

            proj = load_project(args.input)
            out = args.output or (args.input.parent / "book.html")
            html, warnings = render_html(proj.src, theme_name=proj.theme, cwd=cwd,
                                         execute=not args.no_execute, vars=proj.vars,
                                         code_root=proj.code_root,
                                         project_meta=proj.meta)
        else:
            out = args.output or args.input.with_suffix(".html")
            html, warnings = render_html(src, theme_name=args.theme, cwd=cwd,
                                         execute=not args.no_execute)
        Path(out).write_text(html, encoding="utf-8")
        print(f"rendered {out}")
        for w in warnings:
            print(f"  ⚠ {w}", file=sys.stderr)
        return 0

    if args.cmd == "render":
        from .galley import render_pdf

        if args.input.suffix in (".yaml", ".yml"):  # a project
            from .project import load as load_project

            proj = load_project(args.input)
            out = args.output or (args.input.parent / "book.pdf")
            cwd = str(args.input.resolve().parent)
            report = render_pdf(proj.src, str(out), base_url=cwd + "/",
                                theme_name=proj.theme, cwd=cwd,
                                execute=not args.no_execute, vars=proj.vars,
                                code_root=proj.code_root, project_meta=proj.meta)
            print(f"rendered {out} — {report.n_pages} page(s)")
            for w in report.oversized:
                print(f"  ⚠ {w}", file=sys.stderr)
            for w in report.warnings:
                print(f"  ⚠ {w}", file=sys.stderr)
            for w in report.underfull:
                print(f"  ⚠ {w}", file=sys.stderr)
            return 0
        out = args.output or args.input.with_suffix(".pdf")
        cwd = str(args.input.resolve().parent)
        report = render_pdf(src, str(out), base_url=cwd + "/", theme_name=args.theme,
                            cwd=cwd, execute=not args.no_execute)
        print(f"rendered {out} — {report.n_pages} page(s)")
        for w in report.oversized:
            print(f"  ⚠ {w}", file=sys.stderr)
        for w in report.warnings:
            print(f"  ⚠ {w}", file=sys.stderr)
        for w in report.underfull:
            print(f"  ⚠ {w}", file=sys.stderr)
        return 0

    if args.cmd == "tangle":
        if args.test:
            drift = tangle_test(src, args.dir, doc_stem=stem)
            if drift:
                print("tangle drift: " + ", ".join(drift), file=sys.stderr)
                return 1
            print("tangle: up to date")
            return 0
        written = tangle_write(src, args.dir, doc_stem=stem)
        print(f"tangled {len(written)} file(s):")
        for w in written:
            print(f"  {w}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
