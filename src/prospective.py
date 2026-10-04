"""EXP-005 enrollment and operational metadata; never inspect outcomes here."""

import json
from pathlib import Path
from typing import Callable

import exchange_calendars as xcals
import pandas as pd

from src.archive_context import preserve_context, read_context
from src.data import load_parquet
from src.features import build_features
from src.paper_archive import ROOT, load_protocol, verify_run
from src.preservation import canonical_json, digest, get_object, read_record, safe_key, write_record
from src.sessions import due_sessions, session_facts, utc, utc_now

PROTOCOL_HASH = "c85bcb32bbb644f00bbdf0588f88ffee940a7140b20d3a1c732487bfbcaed377"


def protocol() -> dict:
    content = (ROOT / "config/exp005.json").read_bytes().replace(b"\r\n", b"\n")
    if digest(content) != PROTOCOL_HASH:
        raise ValueError("EXP-005 configuration differs from registration")
    load_protocol()  # Also verifies the frozen universe and V1 sources.
    return json.loads(content)


def eligible_session(now: str, requested: str | None = None) -> str:
    """Only the currently open collection window; no historical backfill."""
    stamp = utc(now)
    calendar = xcals.get_calendar("XNYS", start=f"{stamp.year-1}-01-01", end=f"{stamp.year+1}-12-31")
    day = stamp.tz_convert("America/New_York").tz_localize(None).normalize()
    previous = calendar.sessions_in_range(day - pd.Timedelta(days=14), day)
    for candidate in reversed(previous):
        session = candidate.date().isoformat()
        facts = session_facts(session)
        if utc(facts["collection_start"]) <= stamp < utc(facts["next_open"]):
            if session < protocol()["effective_session"]:
                raise ValueError("EXP-005 has not reached its effective session")
            if requested is not None and requested != session:
                raise ValueError("Historical backfill refused in prospective mode")
            return session
    raise ValueError("No eligible completed session: outside collection window")


def volatility_context(stock: pd.DataFrame, spy: pd.DataFrame, session: str) -> dict:
    """Prior-only ticker ATR tertiles, with current/future observations excluded."""
    day = pd.Timestamp(session)
    stock = stock.loc[stock.timestamp.le(day)].copy()
    spy = spy.loc[spy.timestamp.le(day)].copy()
    features = build_features(stock, benchmark=spy)
    rules = protocol()["volatility"]
    values = features["atr_pct_14"]
    history = values.iloc[:-1].tail(rules["lookback"]).dropna()
    ratio = values.iloc[-1]
    valid = len(history) >= rules["minimum_history"] and pd.notna(ratio)
    lower, upper = history.quantile(rules["quantiles"], interpolation="linear") if valid else (None, None)
    group = "unavailable" if not valid else "low" if ratio <= lower else "middle" if ratio <= upper else "high"
    return {"atr_close": None if pd.isna(ratio) else float(ratio),
            "lower": None if lower is None else float(lower),
            "upper": None if upper is None else float(upper), "group": group,
            "prior_valid_observations": len(history)}


def enroll(root: Path, run_id: str, *, clock: Callable[[], str] = utc_now) -> dict:
    """Seal advance protocol/context linkage after publication; never relabel replay."""
    rules = protocol()
    run_id = safe_key(run_id)
    target = root / "exp005" / "decisions" / (run_id + ".json")
    if target.exists():
        return verify_enrollment(root, run_id)
    receipt = verify_run(root, run_id, replay=True)
    intent = read_record(root / "runs" / run_id / "intent.json")
    if intent["mode"] != "collect" or intent["corrects"] or intent["session"] < rules["effective_session"]:
        raise ValueError("Replay, correction or pre-protocol run cannot enroll")
    eligible_session(clock(), intent["session"])
    result = read_record(root / "runs" / run_id / "result.json")
    preserve_context(root, run_id, clock=clock)
    context = read_context(root, run_id)
    frames = {t: load_parquet(root / "objects" / item["validated_sha256"], ticker=t)
              for t, item in result["inputs"].items() if item["status"] == "available"}
    benchmark = load_protocol()["benchmark"]
    groups = {r["ticker"]: volatility_context(frames[r["ticker"]], frames[benchmark], intent["session"])
              if r["status"] == "available" else None for r in result["records"]}
    payload = {"schema_version": 1, "run_id": run_id, "session": intent["session"],
               "protocol_sha256": PROTOCOL_HASH, "parent_sha256": digest(canonical_json(result)),
               "context_sha256": digest(canonical_json(context["payload"])),
               "calculated_at": clock(), "volatility": groups}
    write_record(target, payload)
    published = clock()
    timing_ok = utc(receipt["published_at"]) <= utc(payload["calculated_at"]) <= utc(published) < utc(intent["calendar"]["next_open"])
    classifications = {r["ticker"]: "prospective" if timing_ok
                       and receipt["classifications"].get(r["ticker"]) == "prospective"
                       and context["classifications"].get(r["ticker"]) == "prospective_context"
                       else "excluded" for r in result["records"]}
    write_record(root / "exp005" / "receipts" / (run_id + ".json"),
                 {"decision_sha256": digest(canonical_json(payload)), "published_at": published,
                  "classifications": classifications})
    return verify_enrollment(root, run_id)


def verify_enrollment(root: Path, run_id: str) -> dict:
    """Offline integrity and decision replay; incomplete seals fail closed."""
    protocol()
    run_id = safe_key(run_id)
    parent = verify_run(root, run_id, replay=True)
    intent = read_record(root / "runs" / run_id / "intent.json")
    result = read_record(root / "runs" / run_id / "result.json")
    context = read_context(root, run_id)
    payload = read_record(root / "exp005/decisions" / (run_id + ".json"))
    seal = read_record(root / "exp005/receipts" / (run_id + ".json"))
    fields = {"schema_version", "run_id", "session", "protocol_sha256", "parent_sha256", "context_sha256", "calculated_at", "volatility"}
    if set(payload) != fields or payload["run_id"] != run_id or payload["session"] != intent["session"]:
        raise ValueError("Invalid EXP-005 decision schema")
    if (payload["protocol_sha256"] != PROTOCOL_HASH or intent["mode"] != "collect" or intent["corrects"]
            or payload["session"] < protocol()["effective_session"]
            or payload["parent_sha256"] != digest(canonical_json(result))
            or payload["context_sha256"] != digest(canonical_json(context["payload"]))
            or seal["decision_sha256"] != digest(canonical_json(payload))):
        raise ValueError("EXP-005 linkage changed")
    timing = utc(parent["published_at"]) <= utc(payload["calculated_at"]) <= utc(seal["published_at"]) < utc(intent["calendar"]["next_open"])
    expected = {r["ticker"]: "prospective" if timing and parent["classifications"].get(r["ticker"]) == "prospective"
                and context["classifications"].get(r["ticker"]) == "prospective_context" else "excluded" for r in result["records"]}
    if seal["classifications"] != expected or set(payload["volatility"]) != set(expected):
        raise ValueError("EXP-005 classification mismatch")
    benchmark = load_protocol()["benchmark"]
    for row in result["records"]:
        expected_group = None
        if row["status"] == "available":
            frames = {}
            for t in (row["ticker"], benchmark):
                obj = result["inputs"][t]["validated_sha256"]
                get_object(root, obj)
                frames[t] = load_parquet(root / "objects" / obj, ticker=t)
            expected_group = volatility_context(frames[row["ticker"]], frames[benchmark], intent["session"])
        if payload["volatility"][row["ticker"]] != expected_group:
            raise ValueError("Volatility replay mismatch")
    return {"decision": payload, "receipt": seal}


def operational_summary(root: Path, *, as_of: str) -> dict:
    """Safe frontend export: decisions/coverage only; no premature returns."""
    config = protocol()
    rows, runs = [], []
    for path in sorted((root / "exp005/decisions").glob("*.json")):
        enrolled = verify_enrollment(root, path.stem)
        result = read_record(root / "runs" / path.stem / "result.json")
        context = read_context(root, path.stem)
        contexts = {r["ticker"]: r["context"] for r in context["payload"]["records"]}
        complete = all(v == "prospective" for v in enrolled["receipt"]["classifications"].values())
        runs.append({"run_id": path.stem, "session": enrolled["decision"]["session"], "complete": complete,
                     "published_at": enrolled["receipt"]["published_at"]})
        for row in result["records"]:
            rows.append(row | {"run_id": path.stem, "classification": enrolled["receipt"]["classifications"][row["ticker"]],
                              "published_at": enrolled["receipt"]["published_at"], "context": contexts[row["ticker"]],
                              "volatility": enrolled["decision"]["volatility"][row["ticker"]]})
    genuine = [r for r in rows if r["classification"] == "prospective"]
    events = [r for r in genuine if r["values"]["dip_event_v1"]]
    # Completion counts are read only from integrity-verified outcome records below.
    from src.prospective_outcomes import verified_outcomes
    outcomes = verified_outcomes(root)
    completed = sum(o["paired_complete"] for o in outcomes)
    due = due_sessions(config["effective_session"], as_of)
    return {"protocol": config, "requested_count": len(load_protocol()["universe"]), "runs": runs,
            "records": rows, "days_collected": len(runs), "genuine_records": len(genuine),
            "events": len(events), "non_events": len(genuine)-len(events),
            "failures": len(rows)-len(genuine), "completed_outcomes": completed,
            "pending_outcomes": len(events)-completed, "scheduled_sessions": len(due),
            "complete_runs": sum(r["complete"] for r in runs),
            "latest_collection": max((r["published_at"] for r in runs), default=None),
            "performance_status": "sealed_until_registered_review", "comparison": []}
