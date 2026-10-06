"""Verify EXP-005 hashes, timing, retained inputs and frozen decisions offline."""

import argparse
import json
from pathlib import Path

from src.paper_archive import ROOT
from src.prospective import verify_enrollment
from src.prospective_outcomes import verified_outcomes
from src.scanner import verify_today


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "data/paper_archive")
    parser.add_argument("--run-id")
    parser.add_argument("--snapshot-root", type=Path, help="Verify separate current-market snapshot archive")
    args = parser.parse_args()
    if args.snapshot_root:
        if not args.run_id:
            parser.error("--snapshot-root requires --run-id")
        checked = verify_today(args.snapshot_root, args.run_id)
        print(json.dumps({"verified": True, "snapshot": checked["status"]}, indent=2))
        return
    ids = [args.run_id] if args.run_id else [p.stem for p in (args.root / "exp005/receipts").glob("*.json")]
    checked = []
    for run_id in ids:
        record = verify_enrollment(args.root, run_id)
        if (args.root / "today" / (run_id + ".json")).exists():
            verify_today(args.root, run_id)
        checked.append({"run_id": run_id, "classifications": record["receipt"]["classifications"]})
    outcomes = verified_outcomes(args.root)
    from src.scanner_outcomes import verify_benchmark
    benchmarks = [verify_benchmark(args.root, path) for path in (args.root / "exp005/benchmarks").glob("*/*/*.json")]
    from src.paper_archive import verify_run
    attempts = [verify_run(args.root, p.parent.name, replay=True)["status"]
                for p in (args.root / "runs").glob("*/intent.json")]
    from src.preservation import get_object, read_record
    acquisition_attempts = 0
    for path in (args.root / "runs").glob("*/attempts/*/*.json"):
        item = read_record(path)
        if path.parent.name != item["ticker"]:
            raise ValueError("Acquisition attempt identity mismatch")
        for key in ("raw_sha256", "validated_sha256", "paired_sha256"):
            if key in item:
                get_object(args.root, item[key])
        from src.adjustment import verify_adjustment
        if item['status'] == 'available':
            verify_adjustment(args.root, item)
        acquisition_attempts += 1
    print(json.dumps({"verified": True, "enrollments": checked, "outcome_records": len(outcomes), "benchmark_records": len(benchmarks),
                      "acquisition_attempts_verified": acquisition_attempts,
                      "archive_attempt_statuses": attempts, "performance": "not inspected"}, indent=2))


if __name__ == "__main__":
    main()
