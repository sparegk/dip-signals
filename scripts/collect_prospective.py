"""Collect the current eligible EXP-005 session, or explicitly replay history."""

import argparse
import json
from pathlib import Path

from scripts.archive_signals import collect
from src.paper_archive import ROOT, code_identity
from src.prospective import eligible_session, enroll
from src.sessions import utc_now


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "data/paper_archive")
    parser.add_argument("--mode", choices=["prospective", "historical-replay"], default="prospective")
    parser.add_argument("--as-of", help="Session assertion, never a clock override")
    parser.add_argument("--replay-cache", type=Path)
    args = parser.parse_args()
    if args.mode == "historical-replay":
        if not args.as_of or not args.replay_cache:
            parser.error("historical-replay requires --as-of and --replay-cache")
        result = collect(args.root, session=args.as_of, run_id="replay-" + args.as_of, replay_cache=args.replay_cache)
    else:
        if args.replay_cache:
            parser.error("Prospective mode refuses historical cache inputs")
        try:
            session = eligible_session(utc_now(), args.as_of)
        except ValueError as error:
            parser.error(str(error))
        if code_identity()["dirty"]:
            parser.error("Prospective collection requires a committed clean revision")
        run_id = "exp005-" + session
        collect(args.root, session=session, run_id=run_id)
        checked = enroll(args.root, run_id)
        from collections import Counter
        result = {"run_id":run_id,"session":session,
                  "classifications":dict(Counter(checked["receipt"]["classifications"].values())),
                  "published_at":checked["receipt"]["published_at"],"performance":"not evaluated"}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
