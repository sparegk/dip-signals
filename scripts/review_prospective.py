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
    print(json.dumps(review_report(args.root),indent=2))


if __name__ == "__main__":
    main()
