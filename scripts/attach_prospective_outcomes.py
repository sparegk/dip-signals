"""Acquire separate outcome vintages for original EXP-005 events; no report peeking."""

import argparse
import json
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd

from src.paper_archive import ROOT, capture_input, load_protocol
from src.preservation import read_record
from src.prospective import operational_summary
from src.prospective_outcomes import attach_outcome
from src.sessions import session_facts, utc, utc_now


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "data/paper_archive")
    args = parser.parse_args()
    now = utc(utc_now())
    calendar = xcals.get_calendar("XNYS", start=f"{now.year-1}-01-01", end=f"{now.year+1}-12-31")
    days = calendar.sessions_in_range(now.tz_localize(None).normalize()-pd.Timedelta(days=14), now.tz_localize(None).normalize())
    eligible = [d.date().isoformat() for d in days if utc(session_facts(d.date().isoformat())["collection_start"]) <= now]
    if not eligible:
        parser.error("No completed outcome session")
    cutoff = eligible[-1]
    summary = operational_summary(args.root, as_of=utc_now())
    config = load_protocol()
    acquired, failures, attached = {}, [], 0
    for row in summary["records"]:
        if row["classification"] != "prospective" or not row["values"]["dip_event_v1"] or row["session"] >= cutoff:
            continue
        directory = args.root / "exp005/outcomes" / row["run_id"] / row["ticker"]
        target = directory / (cutoff + ".json")
        if target.exists():
            continue
        prior = [read_record(p) for p in directory.glob("*.json")]
        if prior and max(p["observed_forward_bars"] for p in prior) >= 20:
            continue
        inputs = {}
        for ticker in (row["ticker"], config["benchmark"]):
            if ticker not in acquired:
                acquired[ticker] = capture_input(args.root, ticker, config=config, session=cutoff)
            inputs[ticker] = acquired[ticker]
        if any(item["status"] != "available" for item in inputs.values()):
            failures.append({"record_id": row["record_id"], "inputs": inputs})
            continue
        parent = max(prior, key=lambda p:p["attached_at"])["version"] if prior else None
        attach_outcome(args.root, row["run_id"], row["ticker"], inputs, version=cutoff,
                       corrects=parent, reason="Additional completed bars/new outcome vintage" if parent else None)
        attached += 1
    from src.preservation import write_record
    # Preserve failed attachments without putting them in the evidence sample.
    if failures:
        write_record(args.root / "exp005/outcome_failures" / (now.strftime("%Y%m%dT%H%M%S%f") + ".json"),
                     {"attempted_at": now.isoformat(), "failures": failures})
    print(json.dumps({"attached": attached, "failures": len(failures), "performance": "sealed until registered review"}))


if __name__ == "__main__":
    main()
