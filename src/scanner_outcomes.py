"""Sealed prospective benchmark sidecars for events and retained control decisions."""

from pathlib import Path

import pandas as pd

from src.backtest import apply_costs, compute_forward_outcomes
from src.data import load_parquet
from src.paper_archive import capture_input, code_identity, load_protocol
from src.preservation import canonical_json, digest, get_object, read_record, write_record
from src.prospective import verify_enrollment
from src.scanner import SCANNER_HASH, cash_return, clean, market_clock, verify_today
from src.sessions import session_facts, utc, utc_now


def benchmark_values(stock: pd.DataFrame, spy: pd.DataFrame, session: str, decision: dict,
                     quote: dict | None, available_at: str) -> list[dict]:
    """Original selection only; all future returns remain separate from decisions."""
    for frame in (stock, spy):
        if any(utc(session_facts(t.date().isoformat())["close"]) > utc(available_at) for t in frame.timestamp):
            raise ValueError("Incomplete/future outcome bar")
    data = stock.loc[stock.timestamp.ge(pd.Timestamp(session))].copy()
    if data.empty or data.timestamp.iloc[0] != pd.Timestamp(session):
        raise ValueError("Missing original session in outcome vintage")
    # The outcome engine's eligible selection measures each retained decision;
    # synthetic flags here never enter a scanner or replace original decisions.
    for flag in ("dip_ready_v1", "dip_condition_v1", "dip_event_v1"):
        data[flag] = False
    data.loc[data.index[0], "dip_ready_v1"] = True
    data["dip_component_count"] = 0
    data.loc[data.index[0], "dip_component_count"] = decision["dip_component_count"]
    result = compute_forward_outcomes(data, selection="eligible", benchmark=spy)
    rows = []
    for r in result.to_dict("records"):
        complete = r["status"] == "completed"
        net = apply_costs(r["entry_price"], r["entry_price"]*(1+r["forward_return"]),
                          commission_rate=.0001, slippage_rate=.0005)["net_return"] if complete else None
        cash = cash_return(quote["annual_yield"], r["entry_timestamp"].date().isoformat(),
                           r["end_timestamp"].date().isoformat()) if complete and quote and quote.get("prospective_eligible") else None
        rows.append(clean({"horizon": r["horizon"], "status": r["status"],
                           "entry_session": r["entry_timestamp"].date().isoformat() if complete else None,
                           "end_session": r["end_timestamp"].date().isoformat() if complete else None,
                           "gross": r["forward_return"], "net": net, "spy": r["benchmark_return"],
                           "excess_spy_gross": r["excess_return"], "cash": cash,
                           "excess_cash_net": net-cash if net is not None and cash is not None else None}))
    return rows


def attach_benchmarks(root: Path) -> dict:
    """Append one vintage per current cutoff. Keep non-events and failure records."""
    cutoff = market_clock(utc_now())["latest_completed_session"]
    acquired, attached, failed = {}, 0, []
    config = load_protocol()
    for seal in sorted((root / "exp005/receipts").glob("*.json")):
        enrollment = verify_enrollment(root, seal.stem)
        original = read_record(root / "runs" / seal.stem / "result.json")
        if enrollment["decision"]["session"] >= cutoff:
            continue
        today_path = root / "today" / (seal.stem + ".json")
        today = verify_today(root, seal.stem) if today_path.exists() else None
        for row in original["records"]:
            if enrollment["receipt"]["classifications"][row["ticker"]] != "prospective" or not row["values"]["dip_ready_v1"]:
                continue
            path = root / "exp005/benchmarks" / seal.stem / row["ticker"] / (cutoff + ".json")
            if path.exists():
                verify_benchmark(root, path)
                continue
            prior = [read_record(p) for p in path.parent.glob("*.json")]
            if prior and all(r["status"] == "completed" for r in max(prior, key=lambda p: p["attached_at"])["forward"]):
                continue
            inputs = {}
            for t in (row["ticker"], config["benchmark"]):
                if t not in acquired:
                    acquired[t] = capture_input(root, t, config=config, session=cutoff)
                inputs[t] = acquired[t]
            try:
                if any(i["status"] != "available" or i["latest_session"] != cutoff for i in inputs.values()):
                    raise ValueError("Unavailable or stale benchmark outcome input")
                frames = {t: load_parquet(root / "objects" / i["validated_sha256"], ticker=t) for t, i in inputs.items()}
                now = utc_now()
                values = benchmark_values(frames[row["ticker"]], frames[config["benchmark"]], row["session"], row["values"],
                                          today["treasury"] if today else None, now)
                parent = max(prior, key=lambda p: p["attached_at"]) if prior else None
                payload = {"run_id": seal.stem, "ticker": row["ticker"], "version": cutoff, "attached_at": now,
                           "code": code_identity(),
                           "scanner_sha256": SCANNER_HASH, "decision_sha256": digest(canonical_json(enrollment["decision"])),
                           "today_sha256": digest(canonical_json(today)) if today else None,
                           "parent_sha256": digest(canonical_json(parent)) if parent else None,
                           "selection": "event" if row["values"]["dip_event_v1"] else "condition_non_event" if row["values"]["dip_condition_v1"] else "non_signal",
                           "inputs": inputs, "forward": values}
                write_record(path, payload)
                attached += 1
            except (ValueError, RuntimeError, OSError) as error:
                failed.append({"record_id": row["record_id"], "reason": str(error), "inputs": inputs})
    if failed:
        write_record(root / "exp005/benchmark_failures" / (utc_now().replace(":", "").replace(".", "").replace("+", "") + ".json"),
                     {"failed": failed, "attempted_at": utc_now()})
    return {"attached_benchmark_vintages": attached, "failures": len(failed), "performance": "sealed"}


def verify_benchmark(root: Path, path: Path) -> dict:
    payload = read_record(path)
    enrollment = verify_enrollment(root, payload["run_id"])
    if payload["scanner_sha256"] != SCANNER_HASH or payload["decision_sha256"] != digest(canonical_json(enrollment["decision"])):
        raise ValueError("Benchmark decision linkage mismatch")
    if path.stem != payload["version"] or path.parent.name != payload["ticker"] or path.parent.parent.name != payload["run_id"]:
        raise ValueError("Benchmark identity mismatch")
    if enrollment["receipt"]["classifications"].get(payload["ticker"]) != "prospective":
        raise ValueError("Benchmark decision is not prospective")
    if payload["parent_sha256"]:
        parents = [read_record(p) for p in path.parent.glob("*.json") if p != path]
        parent = next((p for p in parents if digest(canonical_json(p)) == payload["parent_sha256"]), None)
        if parent is None or utc(parent["attached_at"]) >= utc(payload["attached_at"]):
            raise ValueError("Benchmark version parent missing or invalid")
    today = verify_today(root, payload["run_id"]) if payload["today_sha256"] else None
    if today and payload["today_sha256"] != digest(canonical_json(today)):
        raise ValueError("Cash quote linkage mismatch")
    original = read_record(root / "runs" / payload["run_id"] / "result.json")
    row = next(r for r in original["records"] if r["ticker"] == payload["ticker"])
    selection = "event" if row["values"]["dip_event_v1"] else "condition_non_event" if row["values"]["dip_condition_v1"] else "non_signal"
    if payload["selection"] != selection or not row["values"]["dip_ready_v1"]:
        raise ValueError("Benchmark control selection mismatch")
    benchmark = load_protocol()["benchmark"]
    if set(payload["inputs"]) != {payload["ticker"], benchmark}:
        raise ValueError("Benchmark input identities mismatch")
    frames = {}
    for t, i in payload["inputs"].items():
        if i["status"] != "available" or i.get("input_kind") != "new_provider_vintage" or utc(i["provenance"]["retrieved_at"]) > utc(payload["attached_at"]):
            raise ValueError("Invalid benchmark vintage")
        get_object(root, i["validated_sha256"])
        from src.adjustment import verify_adjustment
        verify_adjustment(root, i)
        frames[t] = load_parquet(root / "objects" / i["validated_sha256"], ticker=t)
        if any(utc(session_facts(d.date().isoformat())["close"]) > utc(i["provenance"]["retrieved_at"]) for d in frames[t].timestamp):
            raise ValueError("Benchmark vintage includes bars not closed at retrieval")
    expected = benchmark_values(frames[payload["ticker"]], frames[benchmark], row["session"], row["values"], today["treasury"] if today else None, payload["attached_at"])
    if expected != payload["forward"]:
        raise ValueError("Benchmark outcome replay mismatch")
    return payload


def benchmark_review(root: Path, summary: dict, now: str) -> dict:
    """Publish benchmark performance only on the unchanged registered gated review date."""
    from src.prospective_outcomes import review_allowed
    if not review_allowed(summary, now=now):
        raise ValueError("Benchmark performance review locked")
    target = root / "exp005/benchmark_reviews" / (utc(now).date().isoformat() + ".json")
    if target.exists():
        return read_record(target)
    latest = {}
    for path in (root / "exp005/benchmarks").glob("*/*/*.json"):
        item = verify_benchmark(root, path)
        if utc(item["attached_at"]) > utc(now):
            continue
        key = (item["run_id"], item["ticker"])
        if key not in latest or utc(item["attached_at"]) > utc(latest[key]["attached_at"]):
            latest[key] = item
    rows = [{**r, "selection": i["selection"], "ticker": i["ticker"]}
            for i in latest.values() for r in i["forward"] if r["status"] == "completed"]
    frame = pd.DataFrame(rows)
    tables = []
    if len(frame):
        for horizon, part in frame.groupby("horizon"):
            for name, subset in [("events", part.loc[part.selection.eq("event")]),
                                 ("non_signal", part.loc[part.selection.eq("non_signal")]), ("unconditional", part)]:
                cash = subset.dropna(subset=["excess_cash_net"])
                paired = subset.dropna(subset=["excess_spy_gross"])
                tables.append(clean({"horizon": int(horizon), "selection": name, "count": len(subset),
                                     "mean": subset.gross.mean(), "median": subset.gross.median(),
                                     "net_mean": subset.net.mean(), "spy": paired.spy.mean(),
                                     "spy_excess": paired.excess_spy_gross.mean(), "spy_paired_count": len(paired),
                                     "cash": cash.cash.mean(), "cash_excess": cash.excess_cash_net.mean(), "cash_paired_count": len(cash)}))
    report = {"reviewed_at": now, "scanner_sha256": SCANNER_HASH,
              "gate_coverage": {"scheduled_sessions": summary["scheduled_sessions"], "complete_runs": summary["complete_runs"]},
              "tables": tables, "input_hashes": [digest(canonical_json(i)) for i in latest.values()]}
    write_record(target, report)
    return report


def read_benchmark_review(root: Path, path: Path) -> dict:
    from src.prospective_outcomes import review_allowed
    report = read_record(path)
    if report["scanner_sha256"] != SCANNER_HASH or not review_allowed(report["gate_coverage"], now=report["reviewed_at"]):
        raise ValueError("Invalid benchmark review gate")
    available = {digest(canonical_json(verify_benchmark(root, p))) for p in (root / "exp005/benchmarks").glob("*/*/*.json")}
    if not set(report["input_hashes"]).issubset(available):
        raise ValueError("Benchmark review inputs changed")
    return report
