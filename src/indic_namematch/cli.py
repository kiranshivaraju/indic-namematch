"""Command line entry point: score a pair of names from the shell."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import NameMatcher, __version__
from .matchers import REGISTRY


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="indic-namematch",
        description="Score two Indian names for whether they refer to the same person.",
    )
    parser.add_argument("name_a")
    parser.add_argument("name_b")
    parser.add_argument("--all", action="store_true",
                        help="show every matcher, not just the recommended one")
    parser.add_argument("--explain", action="store_true",
                        help="show the per-token evidence breakdown")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    matcher = NameMatcher()

    if args.all:
        for name, fn in REGISTRY.items():
            print(f"  {name:18} {fn(args.name_a, args.name_b):.3f}")
        print()

    if args.explain:
        print(matcher.explain(args.name_a, args.name_b))
    else:
        score = matcher.score(args.name_a, args.name_b)
        print(f"{score:.3f}  {matcher.bands.decide(score).value.upper()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
