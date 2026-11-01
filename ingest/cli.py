"""Command line entry point.

    python -m ingest run all                 # crosswalk first, then every source
    python -m ingest run bls fred            # just some sources
    python -m ingest run bls --start-year 2010
    python -m ingest sample                  # print a few rows from each latest raw run
    python -m ingest sources                 # list source names
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys

from . import bea, bls, census_acs, fred, metros, oews, postings
from .config import MissingKeyError
from .http import Client
from .landing import latest_run, today

ORDER = ["crosswalk", "bls", "fred", "census_acs", "bea", "oews", "postings"]


def _runners(args):
    return {
        "crosswalk": lambda c: metros.build(c, args.run_date),
        "bls": lambda c: bls.run(c, args.run_date, args.start_year, args.end_year),
        "fred": lambda c: fred.run(c, args.run_date, args.start_year),
        "census_acs": lambda c: census_acs.run(c, args.run_date),
        "bea": lambda c: bea.run(c, args.run_date),
        "oews": lambda c: oews.run(c, args.run_date),
        "postings": lambda c: postings.run(c, args.run_date),
    }


def cmd_run(args) -> int:
    names = ORDER if "all" in args.sources else args.sources
    unknown = set(names) - set(ORDER)
    if unknown:
        print(f"Unknown source(s): {sorted(unknown)}. Choose from {ORDER} or 'all'.")
        return 2
    if "crosswalk" not in names and not metros.METROS_FILE.exists():
        names = ["crosswalk", *names]
    try:
        client = Client()
    except MissingKeyError as e:
        print(e)
        return 1
    runners, failed = _runners(args), []
    for name in [n for n in ORDER if n in names]:
        print(f"==> {name}")
        try:
            runners[name](client)
        except MissingKeyError as e:
            print(f"    skipped: {e}")
            failed.append(name)
        except Exception as e:  # keep going so one broken source doesn't block the rest
            logging.exception("%s failed", name)
            print(f"    FAILED: {e}")
            failed.append(name)
        else:
            run_dir = latest_run(name)
            if run_dir and (run_dir / "_manifest.json").exists():
                man = json.loads((run_dir / "_manifest.json").read_text())
                print(f"    {len(man['files'])} files in {run_dir}")
                for w in man["warnings"][:10]:
                    print(f"    warning: {w}")
    return 1 if failed else 0


def cmd_sample(args) -> int:
    from .sample import show
    for name in (args.sources or ORDER):
        show(name)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m ingest")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="pull sources and land raw files")
    r.add_argument("sources", nargs="+", help=f"'all' or any of {ORDER}")
    r.add_argument("--run-date", default=today(), help="folder name for this run (default: today)")
    r.add_argument("--start-year", type=int, default=2015)
    r.add_argument("--end-year", type=int, default=dt.date.today().year)
    r.add_argument("-v", "--verbose", action="store_true")
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("sample", help="print a few rows from the latest raw run of each source")
    s.add_argument("sources", nargs="*")
    s.set_defaults(func=cmd_sample)

    ls = sub.add_parser("sources", help="list source names")
    ls.set_defaults(func=lambda a: print("\n".join(ORDER)) or 0)

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO if getattr(args, "verbose", False) else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
