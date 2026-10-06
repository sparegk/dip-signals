"""Collect a completed-session snapshot; enroll only within the frozen prospective window."""

import argparse
import json
from pathlib import Path

from scripts.archive_signals import collect
from scripts.build_dashboard_data import build_dashboard
from src.paper_archive import ROOT, code_identity
from src.preservation import canonical_json, digest, read_record, write_record
from src.prospective import enroll, verify_enrollment
from src.scanner import build_today, market_clock, publish_pointer, treasury_quote, verify_today
from src.sessions import utc_now


def run_today(*, snapshot_only: bool = False, offline: bool = False, refresh: bool = False) -> dict:
    """Real clock only. Outside-window snapshots never become prospective evidence."""
    facts = market_clock(utc_now())
    pointer = ROOT / "data/current_market/latest.json"
    if offline:
        if not pointer.exists():
            raise ValueError("No retained current snapshot to verify offline")
        latest = json.loads(pointer.read_bytes())
        snapshot = verify_today(ROOT / latest["root"], latest["run_id"])
        build_dashboard()
        return {"clock": facts, "status": snapshot["status"], "mode": "offline verified retained snapshot"}
    if code_identity()["dirty"]:
        raise ValueError("Daily acquisition requires a committed clean revision")
    session = facts["latest_completed_session"]
    prospective = bool(facts["eligible_session"]) and not snapshot_only
    run_id = "exp005-" + session if prospective else "snapshot-" + session
    if prospective:
        root = ROOT / "data/paper_archive"
    else:
        suffix = "-" + utc_now().replace(":", "").replace(".", "").replace("+", "") if refresh else ""
        root = ROOT / "data/current_market" / (run_id + suffix)
    error = None
    try:
        collect(root, session=session, run_id=run_id)
        if prospective:
            # An already enrolled sealed run can be verified after its window;
            # no duplicate download, new timestamp or relabeling is introduced.
            if (root / "exp005/receipts" / (run_id + ".json")).exists():
                verify_enrollment(root, run_id)
            else:
                enroll(root, run_id)
    except (ValueError, RuntimeError, OSError) as exc:
        error = str(exc)
        if not (root / "runs" / run_id / "intent.json").exists():
            raise
    target = root / "today" / (run_id + ".json")
    quote = read_record(target)["treasury"] if target.exists() else treasury_quote(root, session)
    snapshot = build_today(root, run_id, quote)
    write_record(root / "collection_status" / (run_id + ".json"), snapshot["status"])
    publish_pointer(pointer, {"root": root.relative_to(ROOT).as_posix(), "run_id": run_id,
                              "sha256": digest(canonical_json(snapshot))})
    build_dashboard()
    report = {"clock": facts, "status": snapshot["status"],
              "mode": "prospective collection" if prospective else "snapshot only — excluded from EXP-005 enrollment",
              "candidates": [{"ticker": r["ticker"], "features": r["features"], "reference": r["reference"]}
                             for r in snapshot["rows"] if r["features"] and r["features"]["dip_event_v1"]],
              "failures": [{"ticker": r["ticker"], "reason": r["error"]} for r in snapshot["rows"] if r["status"] != "available"],
              "treasury": quote, "error": error}
    print(json.dumps(report, indent=2))
    if error or snapshot["status"]["completion_status"] != "complete":
        raise RuntimeError("Collection incomplete; all failures retained and exported")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-only", action="store_true", help="Never enroll, even inside collection window")
    parser.add_argument("--offline", action="store_true", help="Verify retained snapshot and re-export, without network")
    parser.add_argument("--refresh", action="store_true", help="New snapshot vintage; cannot replace a prospective original")
    args = parser.parse_args()
    try:
        result = run_today(**vars(args))
        if args.offline:
            print(json.dumps(result, indent=2))
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
