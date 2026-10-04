"""Separate immutable EXP-005 outcomes, using the existing execution engine."""

import json
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from src.backtest import compute_forward_outcomes, simulate_barrier_trades
from src.data import load_parquet
from src.paper_archive import load_protocol
from src.preservation import canonical_json, digest, get_object, read_record, safe_key, write_record
from src.prospective import PROTOCOL_HASH, protocol, verify_enrollment
from src.sessions import session_facts, utc, utc_now


def json_rows(frame: pd.DataFrame) -> list[dict]:
    """Serialize missing outcomes as null, dates as ISO strings."""
    return json.loads(frame.to_json(orient="records", date_format="iso", double_precision=15))


def event_outcomes(stock: pd.DataFrame, spy: pd.DataFrame, *, session: str,
                   component_count: int, available_at: str) -> dict:
    """Use only closed bars and an ORIGINAL event, never regenerate selection."""
    cutoff = utc(available_at)
    for frame in (stock, spy):
        for stamp in frame.timestamp:
            if utc(session_facts(stamp.date().isoformat())["close"]) > cutoff:
                raise ValueError("Outcome vintage contains incomplete/future bars")
    data = stock.loc[stock.timestamp.ge(pd.Timestamp(session))].copy()
    if data.empty or data.timestamp.iloc[0] != pd.Timestamp(session):
        raise ValueError("Outcome vintage lacks original signal session")
    for flag in ("dip_event_v1", "dip_condition_v1", "dip_ready_v1"):
        data[flag] = np.arange(len(data)) == 0
    data["dip_component_count"] = np.where(data.dip_event_v1, component_count, 0)
    rules = protocol()
    forward = compute_forward_outcomes(data, horizons=rules["horizons"], benchmark=spy)
    paired_complete = len(data) >= 11
    policies = {}
    for name, specification in rules["policies"].items():
        trades = simulate_barrier_trades(data, **specification, commission_rate=rules["commission_bps"] / 10000,
                                        slippage_rate=rules["slippage_bps"] / 10000)
        policies[name] = json_rows(trades)
    # Paths are diagnostic only and cannot alter the original event/policies.
    path = data.iloc[1:21]
    timing = {}
    if len(path):
        entry = path.open.iloc[0]
        for threshold in (0, .02, .05, .10):
            hits = np.flatnonzero(path.close.to_numpy() / entry - 1 > threshold) if threshold == 0 else np.flatnonzero(path.high.to_numpy() / entry - 1 >= threshold)
            timing[str(threshold)] = int(hits[0] + 1) if len(hits) else None
    return {"forward": json_rows(forward), "policies": policies, "paired_complete": paired_complete,
            "timing": timing, "observed_forward_bars": len(data)-1}


def attach_outcome(root: Path, run_id: str, ticker: str, inputs: dict, *, version: str,
                   corrects: str | None = None, reason: str | None = None,
                   clock: Callable[[], str] = utc_now) -> dict:
    """Append an outcome vintage; originals and decision bytes remain unchanged."""
    run_id, ticker, version = map(safe_key, (run_id, ticker, version))
    enrollment = verify_enrollment(root, run_id)
    original = read_record(root / "runs" / run_id / "result.json")
    decision = next(r for r in original["records"] if r["ticker"] == ticker)
    if enrollment["receipt"]["classifications"][ticker] != "prospective" or not decision["values"]["dip_event_v1"]:
        raise ValueError("Only original EXP-005 prospective events receive outcomes")
    path = root / "exp005/outcomes" / run_id / ticker / (version + ".json")
    if path.exists():
        existing = read_record(path)
        if existing["inputs"] != inputs or existing["corrects"] != corrects or existing["reason"] != reason:
            raise ValueError("Conflicting outcome retry; append an explicit new version")
        return verify_outcome(root, path)
    previous = sorted(path.parent.glob("*.json"))
    if previous and not corrects:
        raise ValueError("New outcome vintage requires parent version and reason")
    if corrects:
        safe_key(corrects)
        if not reason or not (path.parent / (corrects + ".json")).exists():
            raise ValueError("Correction requires an existing parent and reason")
    benchmark = load_protocol()["benchmark"]
    if set(inputs) != {ticker, benchmark}:
        raise ValueError("Outcome needs exact stock and benchmark vintages")
    attached = clock()
    frames = {}
    for t, item in inputs.items():
        if item["status"] != "available" or item.get("input_kind") != "new_provider_vintage":
            raise ValueError("Unavailable/replay outcome input")
        if utc(item["provenance"]["retrieved_at"]) > utc(attached):
            raise ValueError("Future retrieval timestamp")
        get_object(root, item["validated_sha256"])
        frames[t] = load_parquet(root / "objects" / item["validated_sha256"], ticker=t)
        if utc(session_facts(frames[t].timestamp.max().date().isoformat())["close"]) > utc(item["provenance"]["retrieved_at"]):
            raise ValueError("Outcome bars were not closed at retrieval")
    values = event_outcomes(frames[ticker], frames[benchmark], session=decision["session"],
                            component_count=decision["values"]["dip_component_count"], available_at=attached)
    old_obj = original["inputs"][ticker]["validated_sha256"]
    old = load_parquet(root / "objects" / old_obj, ticker=ticker)
    original_close = float(old.loc[old.timestamp.eq(pd.Timestamp(decision["session"])), "close"].iloc[0])
    revised_close = float(frames[ticker].loc[frames[ticker].timestamp.eq(pd.Timestamp(decision["session"])), "close"].iloc[0])
    payload = {"schema_version": 1, "run_id": run_id, "ticker": ticker, "version": version,
               "corrects": corrects, "reason": reason, "attached_at": attached,
               "protocol_sha256": PROTOCOL_HASH, "decision_sha256": digest(canonical_json(enrollment["decision"])),
               "inputs": inputs, "signal_close_revision": revised_close / original_close - 1, **values}
    write_record(path, payload)
    return payload


def verify_outcome(root: Path, path: Path) -> dict:
    payload = read_record(path)
    enrollment = verify_enrollment(root, payload["run_id"])
    if payload["protocol_sha256"] != PROTOCOL_HASH or payload["decision_sha256"] != digest(canonical_json(enrollment["decision"])):
        raise ValueError("Outcome linkage mismatch")
    if enrollment["receipt"]["classifications"].get(payload["ticker"]) != "prospective":
        raise ValueError("Outcome linked to retrospective decision")
    for item in payload["inputs"].values():
        for key in ("validated_sha256", "raw_sha256"):
            if key in item:
                get_object(root, item[key])
    original = read_record(root / "runs" / payload["run_id"] / "result.json")
    row = next(r for r in original["records"] if r["ticker"] == payload["ticker"])
    if not row["values"]["dip_event_v1"]:
        raise ValueError("Outcome must reference an original event")
    benchmark = load_protocol()["benchmark"]
    frames = {t:load_parquet(root / "objects" / item["validated_sha256"], ticker=t)
              for t,item in payload["inputs"].items()}
    expected = event_outcomes(frames[payload["ticker"]],frames[benchmark],session=row["session"],
                               component_count=row["values"]["dip_component_count"],available_at=payload["attached_at"])
    if any(payload.get(key) != value for key,value in expected.items()):
        raise ValueError("Outcome replay mismatch")
    return payload


def verified_outcomes(root: Path) -> list[dict]:
    """Latest explicit version per event; all older versions remain retained."""
    latest = {}
    for path in sorted((root / "exp005/outcomes").glob("*/*/*.json")):
        item = verify_outcome(root, path)
        key = (item["run_id"], item["ticker"])
        if key not in latest or utc(item["attached_at"]) > utc(latest[key]["attached_at"]):
            latest[key] = item
    return list(latest.values())


def review_allowed(summary: dict, *, now: str) -> bool:
    """Fixed dates and all-name operational coverage; count alone never opens review."""
    rules = protocol()
    day = utc(now).date().isoformat()
    sessions = summary["scheduled_sessions"]
    return (day in rules["review_dates"] and sessions >= rules["minimum_scheduled_sessions"]
            and summary["complete_runs"] / max(sessions, 1) >= rules["minimum_complete_run_fraction"])


def review_report(root: Path, *, clock: Callable[[], str] = utc_now) -> dict:
    """Only registered gated dates may unblind aggregate outcome statistics."""
    from src.metrics import summarize_returns, trade_metrics
    from src.prospective import operational_summary
    now = clock()
    summary = operational_summary(root,as_of=now)
    if not review_allowed(summary,now=now):
        raise ValueError("Performance review locked: registered date/coverage gate unmet")
    target = root / "exp005/reviews" / (utc(now).date().isoformat()+".json")
    if target.exists():
        return read_record(target)
    rows = {r["record_id"]:r for r in summary["records"]}
    selected = verified_outcomes(root)
    trades, forward = [], []
    for outcome in selected:
        record = rows[outcome["run_id"]+":"+outcome["ticker"]]
        group = record["volatility"]["group"]
        for item in outcome["forward"]:
            forward.append(item | {"volatility":group})
        if outcome["paired_complete"]:
            for name, policy in outcome["policies"].items():
                trades.append(policy[0] | {"policy":name,"volatility":group,"session":record["session"]})
    frame = pd.DataFrame(trades)
    results = []
    for column in (None,"ticker","volatility","calendar_period"):
        if frame.empty:
            break
        frame["calendar_period"] = pd.to_datetime(frame.session).dt.to_period("Q").astype(str)
        for key, subset in frame.groupby(["policy"] + ([column] if column else []),sort=True):
            for date in ("entry_timestamp","exit_timestamp"):
                subset = subset.copy(); subset[date] = pd.to_datetime(subset[date])
            metrics = trade_metrics(subset)
            metrics.update(fifth_percentile=float(subset.net_return.quantile(.05)),worst_loss=float(subset.net_return.min()))
            results.append({"policy":key[0],"grouping":column or "all","group":key[1] if column else "all", **metrics})
    forwards = pd.DataFrame(forward)
    horizon_summary = []
    if not forwards.empty:
        for (horizon,group), subset in forwards.groupby(["horizon","volatility"]):
            complete = subset.loc[subset.status.eq("completed")]
            paired = complete.loc[complete.excess_return.notna()]
            horizon_summary.append({"horizon":horizon,"group":group,"count":len(complete),
                "mean":complete.forward_return.mean(),"median":complete.forward_return.median(),
                "matched_spy_excess":paired.excess_return.mean(),"mfe":complete.mfe.mean(),"mae":complete.mae.mean()})
    paired_ev = {}
    if not frame.empty:
        pivot = frame.pivot(index=["session","ticker"],columns="policy",values="net_return")
        difference = pivot.ten_bar_hold-pivot.historical_v1_control
        paired_ev = summarize_returns(difference,dates= pivot.index.get_level_values("session"),block_size=20,seed=42)
    report = {"reviewed_at":now,"protocol_sha256":PROTOCOL_HASH,"completed_events":summary["completed_outcomes"],
              "milestones_crossed":[n for n in protocol()["review_event_milestones"] if summary["completed_outcomes"]>=n],
              "comparison":json_rows(pd.DataFrame(results)),"forward":json_rows(pd.DataFrame(horizon_summary)),
              "paired_ev":json_rows(pd.DataFrame([paired_ev]))[0] if paired_ev else {},
              "outcome_hashes":[digest(canonical_json(o)) for o in selected]}
    write_record(target,report)
    return report
