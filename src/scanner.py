"""Daily research snapshots and prior-only references, separate from enrollment."""

import calendar as calendar_dates
import json
import os
from pathlib import Path
import tempfile
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import exchange_calendars as xcals
import numpy as np
import pandas as pd

from src.backtest import compute_forward_outcomes, simulate_barrier_trades
from src.data import load_parquet
from src.features import build_features
from src.paper_archive import ROOT, load_protocol, verify_run
from src.preservation import canonical_json, digest, get_object, put_object, read_record, write_record
from src.prospective import protocol, volatility_context
from src.research_diagnosis import rebound_paths
from src.sessions import session_facts, utc, utc_now
from src.signals import build_signals

SCANNER_HASH = "76fc319b6122a2be333d96104a21c8f0a7812f8499972209540b8275ca2ee6b6"


def scanner_protocol() -> dict:
    content = (ROOT / "config/scanner.json").read_bytes().replace(b"\r\n", b"\n")
    if digest(content) != SCANNER_HASH:
        raise ValueError("Registered scanner configuration changed")
    return json.loads(content)


def market_clock(now: str) -> dict:
    """Separate completed session, intraday state and the registered enrollment window."""
    stamp = utc(now)
    cal = xcals.get_calendar("XNYS", start=f"{stamp.year-1}-01-01", end=f"{stamp.year+1}-12-31")
    day = stamp.tz_convert("America/New_York").tz_localize(None).normalize()
    days = cal.sessions_in_range(day - pd.Timedelta(days=14), day + pd.Timedelta(days=14))
    closed = [d for d in days if cal.session_close(d) <= stamp]
    session = closed[-1].date().isoformat()
    facts = session_facts(session)
    next_day = next(d for d in days if cal.session_open(d) > stamp)
    current = cal.is_session(day) and cal.session_open(day) <= stamp < cal.session_close(day)
    eligible = utc(facts["collection_start"]) <= stamp < utc(facts["next_open"])
    if stamp < utc(facts["collection_start"]):
        window = facts
    elif eligible:
        window = facts
    else:
        upcoming = next(d for d in days if cal.session_close(d) > stamp)
        window = session_facts(upcoming.date().isoformat())
    return {"as_of": stamp.isoformat(), "latest_completed_session": session,
            "market_state": "open — intraday bar excluded" if current else "closed",
            "intraday_context": "unavailable — completed daily bars only",
            "eligible_session": session if eligible and session >= protocol()["effective_session"] else None,
            "next_session": next_day.date().isoformat(),
            "next_market_open": cal.session_open(next_day).isoformat(),
            "collection_window_start": window["collection_start"],
            "collection_window_end": window["next_open"]}


def cash_return(annual_yield: float, entry: str, exit: str) -> float:
    """Simple ACT/ACT accrual, using actual elapsed calendar days, never bars/252."""
    if not np.isfinite(annual_yield) or not 0 <= annual_yield <= 1:
        raise ValueError("Invalid annual investment yield")
    start, end = pd.Timestamp(entry).normalize(), pd.Timestamp(exit).normalize()
    if start.tzinfo or end.tzinfo or end < start:
        raise ValueError("Cash endpoints must be ordered naive dates")
    fraction = 0.
    while start < end:
        boundary = min(end, pd.Timestamp(year=start.year+1, month=1, day=1))
        fraction += (boundary-start).days / (366 if calendar_dates.isleap(start.year) else 365)
        start = boundary
    return annual_yield * fraction


def parse_treasury(content: bytes, session: str) -> dict:
    """Official investment yield only; never use bank-discount yield as a return."""
    rates = []
    for entry in ET.fromstring(content).iter():
        if entry.tag.split("}")[-1] != "properties":
            continue
        fields = {e.tag.split("}")[-1]: e.text for e in entry}
        date = (fields.get(scanner_protocol()["treasury"]["date_field"]) or "")[:10]
        value = fields.get(scanner_protocol()["treasury"]["field"])
        if date and value and date <= session:
            rate = float(value) / 100
            if not np.isfinite(rate) or not 0 <= rate <= 1:
                raise ValueError("Invalid Treasury yield")
            rates.append((date, rate))
    if not rates:
        raise ValueError("No decision-date 13-week investment yield")
    date, rate = max(rates)
    if (pd.Timestamp(session)-pd.Timestamp(date)).days > scanner_protocol()["treasury"]["maximum_age_calendar_days"]:
        raise ValueError("Treasury quote is stale")
    return {"status": "available", "rate_date": date, "annual_yield": rate,
            "method": scanner_protocol()["treasury"]["method"]}


def treasury_quote(root: Path, session: str) -> dict:
    """Retain response bytes and retrieval time; failures are explicit, with no fallback."""
    rules = scanner_protocol()["treasury"]
    url = f"{rules['source']}?data={rules['series']}&field_tdr_date_value={session[:4]}"
    result = {"source": url, "status": "unavailable", "annual_yield": None}
    try:
        with urlopen(Request(url, headers={"User-Agent": "DipSignal research/1.0"}), timeout=30) as response:
            content = response.read(8_000_001)
        if len(content) > 8_000_000:
            raise ValueError("Treasury response exceeds size limit")
        result.update(raw_sha256=put_object(root, content), retrieved_at=utc_now())
        result.update(parse_treasury(content, session))
    except (OSError, ValueError, ET.ParseError) as error:
        result["error"] = f"{type(error).__name__}: {error}"
    return result


def clean(value):
    """JSON-safe finite research quantities."""
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, np.generic):
        value = value.item()
    return None if isinstance(value, float) and not np.isfinite(value) else value


def describe(rows: pd.DataFrame) -> dict:
    complete = rows.loc[rows.status.eq("completed")]
    paired = complete.dropna(subset=["excess_return"])
    return clean({"count": len(complete), "mean": complete.forward_return.mean(),
                  "median": complete.forward_return.median(),
                  "win_rate": complete.forward_return.gt(0).mean() if len(complete) else None,
                  "mfe": complete.mfe.mean(), "mae": complete.mae.mean(),
                  "spy": paired.benchmark_return.mean(), "excess": paired.excess_return.mean(),
                  "spy_median": paired.benchmark_return.median(),
                  "paired_count": len(paired)})


def reference_tables(signals: pd.DataFrame, spy: pd.DataFrame, session: str) -> tuple[dict, pd.DataFrame, list[float]]:
    """Exclude signal day and all prospective-era outcomes before any calculation."""
    cutoff = min(session, scanner_protocol()["historical_reference_end_exclusive"])
    history = signals.loc[signals.timestamp.lt(pd.Timestamp(cutoff))].copy()
    benchmark = spy.loc[spy.timestamp.lt(pd.Timestamp(cutoff))].copy()
    minimum = scanner_protocol()["minimum_same_ticker_events"]
    tables = []
    for selection in ("events", "non_signal", "eligible"):
        tables.append(compute_forward_outcomes(history, selection=selection, benchmark=benchmark))
    combined = pd.concat(tables, ignore_index=True)
    event = tables[0]
    # Context groups use causal prior ATR boundaries; no conditional signal filter.
    prior_atr = history.atr_pct_14.shift(1).rolling(252, min_periods=126)
    lower, upper = prior_atr.quantile(1/3), prior_atr.quantile(2/3)
    groups = pd.Series(np.where(history.atr_pct_14.le(lower), "low",
                               np.where(history.atr_pct_14.le(upper), "middle", "high")), index=history.index)
    groups.loc[lower.isna() | upper.isna() | history.atr_pct_14.isna()] = "unavailable"
    context_by_day = dict(zip(history.timestamp, groups))
    volatility_rows = []
    contextual = event.copy()
    contextual["volatility_group"] = contextual.timestamp.map(context_by_day)
    for (h, group), part in contextual.groupby(["horizon", "volatility_group"]):
        stats = describe(part)
        volatility_rows.append({"horizon": int(h), "group": group,
                                "status": "available" if stats["count"] >= minimum else "insufficient",
                                **(stats if stats["count"] >= minimum else {"count": stats["count"]})})
    summaries = []
    for h, rows in event.groupby("horizon"):
        stats = describe(rows)
        summaries.append({"horizon": int(h), "status": "available" if stats["count"] >= minimum else "insufficient",
                          **(stats if stats["count"] >= minimum else {"count": stats["count"]})})
    rules = protocol()
    # Require full ten-bar maturity even for an earlier barrier exit.
    mature_dates = set(event.loc[event.horizon.eq(10) & event.status.eq("completed"), "timestamp"])
    trades = simulate_barrier_trades(history, **rules["policies"]["historical_v1_control"],
                                     commission_rate=rules["commission_bps"]/10000,
                                     slippage_rate=rules["slippage_bps"]/10000)
    mature_trades = trades.loc[trades.timestamp.isin(mature_dates)]
    net = mature_trades.net_return.tolist() if len(mature_trades) else []
    ten = event.loc[event.horizon.eq(10) & event.status.eq("completed")]
    envelope = None
    if len(ten) >= minimum:
        mae = ten.mae.quantile([.25, .5, .75]).tolist()
        mfe = ten.mfe.quantile([.25, .5, .75]).tolist()
        envelope = clean({"count": len(ten), "mae_quartiles": mae, "mfe_quartiles": mfe,
                          "median_mfe_mae_ratio": abs(mfe[1]/mae[1]) if mae[1] else None})
    history["fold"] = "historical_reference"
    paths = rebound_paths(history, {"path_bars": 20, "rebound_levels": [.02, .05, .10]})
    timing = []
    if len(paths) >= minimum:
        for level in (2, 5, 10):
            values = paths[f"reach_{level}pct"].dropna()
            timing.append(clean({"level": level, "complete_paths": len(paths), "reached": len(values),
                                 "median_bars_if_reached": values.median()}))
    return clean({"cutoff_exclusive": cutoff, "minimum_events": minimum,
                  "previous_events": int(history.dip_event_v1.sum()), "horizons": summaries,
                  "volatility_horizons": volatility_rows,
                  "v1_net_ev": float(np.mean(net)) if len(net) >= minimum else None,
                  "v1_count": len(net), "average_holding_bars": mature_trades.holding_bars.mean() if len(net) >= minimum else None,
                  "envelope": envelope, "timing": timing}), combined, net


def scan_frames(frames: dict[str, pd.DataFrame], inputs: dict, session: str) -> dict:
    """Deterministic scanner. Future bars cannot change decisions or reference context."""
    config = load_protocol()
    spy = frames.get(config["benchmark"])
    rows, historical, all_net = [], [], []
    for ticker in config["universe"]:
        item = inputs.get(ticker, {})
        stock = frames.get(ticker)
        record = {"ticker": ticker, "status": "unavailable", "error": item.get("error") or "Input unavailable",
                  "features": None, "reference": None, "volatility": None,
                  "retrieved_at": item.get("provenance", {}).get("retrieved_at"),
                  "latest_session": item.get("latest_session"), "input_hash": item.get("validated_sha256")}
        if stock is not None and spy is not None:
            stock = stock.loc[stock.timestamp.le(pd.Timestamp(session))].copy()
            benchmark = spy.loc[spy.timestamp.le(pd.Timestamp(session))].copy()
            if stock.empty or benchmark.empty or stock.timestamp.max() != pd.Timestamp(session) or benchmark.timestamp.max() != pd.Timestamp(session):
                record.update(status="stale", error="Completed-session stock or SPY bar missing")
            else:
                signal = build_signals(build_features(stock, benchmark=benchmark), **config["signal_parameters"])
                latest = signal.iloc[-1]
                fields = ["close", "volume", "return_1d", "drawdown_20d", "drawdown_60d", "price_zscore_20d",
                          "distance_from_low_20d", "relative_return_10d", "atr_14", "atr_pct_14", "relative_volume_20d"]
                fields += [c for c in signal.columns if c.startswith("dip_") or c.endswith("_threshold")]
                ref, table, net = reference_tables(signal, benchmark, session)
                historical.append(table)
                all_net.extend(net)
                record.update(status="available", error=None, features=clean({c: latest[c] for c in fields}),
                              volatility=volatility_context(stock, benchmark, session), reference=ref)
        elif stock is not None:
            record["error"] = "SPY unavailable: " + str(inputs.get(config["benchmark"], {}).get("error"))
        rows.append(record)
    edge = []
    if historical:
        table = pd.concat(historical, ignore_index=True)
        for h in scanner_protocol()["horizons"]:
            groups = {s: describe(table.loc[table.horizon.eq(h) & table.selection.eq(s)])
                      for s in ("events", "non_signal", "eligible")}
            event, non, unconditional = (groups[s] for s in ("events", "non_signal", "eligible"))
            edge.append(clean({"horizon": h, **event, "non_signal": non["mean"], "non_signal_median": non["median"],
                               "non_signal_count": non["count"], "unconditional": unconditional["mean"],
                               "unconditional_median": unconditional["median"], "unconditional_count": unconditional["count"],
                               "difference_non_signal": event["mean"]-non["mean"] if event["mean"] is not None and non["mean"] is not None else None}))
    context = None
    if spy is not None:
        prefix = spy.loc[spy.timestamp.le(pd.Timestamp(session))]
        if len(prefix) and prefix.timestamp.max() == pd.Timestamp(session):
            last = build_features(prefix).iloc[-1]
            mean = prefix.close.tail(200).mean() if len(prefix) >= 200 else None
            context = clean({"close": last.close, "return_1d": last.return_1d, "atr_pct_14": last.atr_pct_14,
                             "regime": "unknown" if mean is None else "above SMA200" if last.close >= mean else "below SMA200"})
    return {"session": session, "rows": rows, "edge": edge, "spy": context,
            "historical_universe_available": len(historical),
            "historical_v1_count": len(all_net), "historical_v1_net_ev": float(np.mean(all_net)) if all_net else None,
            "adaptive_reference": "Unavailable: EXP-004 has fold-varying winners; no single prospective policy registered"}


def collection_status(root: Path, run_id: str) -> dict:
    """Retain partial/interrupted attempts; success requires all 95 decisions, not just inputs."""
    directory = root / "runs" / run_id
    intent = read_record(directory / "intent.json")
    verified = verify_run(root, run_id, replay=True)
    result = read_record(directory / "result.json") if (directory / "result.json").exists() else None
    rows = result["records"] if result else []
    available = sum(r["status"] == "available" for r in rows)
    event_count = sum(bool(r["values"]["dip_event_v1"]) for r in rows if r["status"] == "available")
    return {"session_date": intent["session"], "collection_started": intent["started_at"],
            "collection_completed": verified.get("published_at"), "completion_status": verified["status"],
            "expected_tickers": len(intent["universe"]), "successful_tickers": available,
            "failed_tickers": len(intent["universe"])-available, "signal_count": event_count,
            "non_event_count": available-event_count, "data_source": "yfinance adjusted daily OHLCV",
            "configuration_hash": intent["config_sha256"], "code": intent["code"],
            "expected_entry_timestamp": intent["calendar"]["next_open"],
            "run_id": run_id, "classifications": verified.get("classifications", {})}


def build_today(root: Path, run_id: str, treasury: dict) -> dict:
    """Derived snapshot uses retained vintages and is immutable; original archive is untouched."""
    status = collection_status(root, run_id)
    intent = read_record(root / "runs" / run_id / "intent.json")
    path = root / "today" / (run_id + ".json")
    if path.exists():
        return verify_today(root, run_id)
    inputs = {}
    for p in (root / "runs" / run_id / "inputs").glob("*.json"):
        inputs[p.stem] = read_record(p)
    frames = {}
    for ticker, item in inputs.items():
        if item["status"] == "available":
            get_object(root, item["validated_sha256"])
            frames[ticker] = load_parquet(root / "objects" / item["validated_sha256"], ticker=ticker)
    scan = scan_frames(frames, inputs, intent["session"])
    quote = dict(treasury)
    if quote["status"] == "available":
        if utc(quote["retrieved_at"]) >= utc(intent["calendar"]["next_open"]):
            quote["prospective_eligible"] = False
        else:
            quote["prospective_eligible"] = True
        quote["scenarios"] = cash_scenarios(quote["annual_yield"], intent["session"])
    calculated = utc_now()
    if quote["status"] == "available":
        quote["prospective_eligible"] = quote["prospective_eligible"] and utc(calculated) < utc(intent["calendar"]["next_open"])
    payload = clean({"schema_version": 1, "scanner_sha256": SCANNER_HASH,
                     "status": status, "snapshot_kind": "Current Market Snapshot",
                     "calculated_at": calculated, "treasury": quote, **scan})
    write_record(path, payload)
    return payload


def cash_scenarios(rate: float, session: str) -> list[dict]:
    day = pd.Timestamp(session)
    cal = xcals.get_calendar("XNYS", start=session, end=f"{day.year+1}-12-31")
    days = cal.sessions_in_range(cal.next_session(day), day + pd.Timedelta(days=60))
    return [{"horizon": h, "entry_session": days[0].date().isoformat(),
             "exit_session": days[h-1].date().isoformat(),
             "return": cash_return(rate, days[0].date().isoformat(), days[h-1].date().isoformat())}
            for h in scanner_protocol()["horizons"]]


def verify_today(root: Path, run_id: str) -> dict:
    """Replay scanner from retained inputs and validate the rate's retained source."""
    payload = read_record(root / "today" / (run_id + ".json"))
    if payload["scanner_sha256"] != SCANNER_HASH or payload["status"] != collection_status(root, run_id):
        raise ValueError("Scanner linkage changed")
    inputs = {p.stem: read_record(p) for p in (root / "runs" / run_id / "inputs").glob("*.json")}
    frames = {}
    for ticker, item in inputs.items():
        if item["status"] == "available":
            get_object(root, item["validated_sha256"])
            frames[ticker] = load_parquet(root / "objects" / item["validated_sha256"], ticker=ticker)
    expected = scan_frames(frames, inputs, payload["session"])
    if any(payload[k] != v for k, v in expected.items()):
        raise ValueError("Scanner decision/reference replay mismatch")
    quote = payload["treasury"]
    if quote["status"] == "available":
        parsed = parse_treasury(get_object(root, quote["raw_sha256"]), payload["session"])
        if any(quote[k] != v for k, v in parsed.items()) or quote["scenarios"] != cash_scenarios(quote["annual_yield"], payload["session"]):
            raise ValueError("Treasury replay mismatch")
    return payload


def publish_pointer(path: Path, payload: dict) -> None:
    """Replace a derived latest pointer atomically; evidence itself is never replaced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".latest-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical_json(payload))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def export_today(project: Path, as_of: str) -> dict:
    """Offline compact export; stale snapshots are not presented as current sessions."""
    clock = market_clock(as_of)
    pointer = project / "data/current_market/latest.json"
    if not pointer.exists():
        return {"clock": clock, "snapshot": None, "warning": "No current market snapshot collected"}
    latest = json.loads(pointer.read_bytes())
    root = project / latest["root"]
    if not root.resolve().is_relative_to((project / "data").resolve()):
        raise ValueError("Snapshot root outside data directory")
    payload = read_record(root / "today" / (latest["run_id"] + ".json"))
    if digest(canonical_json(payload)) != latest["sha256"]:
        raise ValueError("Latest snapshot hash mismatch")
    warning = None if payload["session"] == clock["latest_completed_session"] else "Stale snapshot — latest completed session has not been collected"
    return {"clock": clock, "snapshot": payload, "warning": warning}
