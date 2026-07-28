"""scriptorium CLI (VS1): `scriptorium render <in.md> -o <out.pdf>`."""

import argparse
import sys
from pathlib import Path

from .galley import render_pdf


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="scriptorium")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render", help="render a Markdown file to PDF")
    r.add_argument("input", type=Path)
    r.add_argument("-o", "--output", type=Path, default=None)
    args = p.parse_args(argv)

    if args.cmd == "render":
        out = args.output or args.input.with_suffix(".pdf")
        base_url = str(args.input.resolve().parent) + "/"
        report = render_pdf(args.input.read_text(encoding="utf-8"), str(out), base_url=base_url)
        print(f"rendered {out} — {report.n_pages} page(s)")
        for w in report.oversized:
            print(f"  ⚠ oversized: {w}", file=sys.stderr)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
