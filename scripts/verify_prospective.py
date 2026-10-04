"""Verify EXP-005 hashes, timing, retained inputs and frozen decisions offline."""

import argparse
import json
from pathlib import Path

from src.paper_archive import ROOT
from src.prospective import verify_enrollment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "data/paper_archive")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    checked = verify_enrollment(args.root, args.run_id)
    print(json.dumps({"run_id": args.run_id, "verified": True,
                      "classifications": checked["receipt"]["classifications"]}, indent=2))


if __name__ == "__main__":
    main()
