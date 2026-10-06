"""Unblind EXP-005 only at its registered date and coverage gates."""

import argparse
import json
from pathlib import Path

from src.paper_archive import ROOT
from src.prospective_outcomes import review_report


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT/"data/paper_archive")
    args=parser.parse_args()
    report = review_report(args.root)
    from src.prospective import operational_summary
    from src.scanner_outcomes import benchmark_review
    from src.sessions import utc_now
    now = utc_now()
    benchmarks = benchmark_review(args.root, operational_summary(args.root, as_of=now), now)
    print(json.dumps({"exit_review": report, "benchmark_review": benchmarks}, indent=2))


if __name__ == "__main__":
    main()
