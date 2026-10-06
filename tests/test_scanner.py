"""Daily scanner clocks, leakage, cash arithmetic and retained-vintage integrity."""

from copy import deepcopy

import pandas as pd
import pytest

from test_prospective import enrolled, prices
from src import scanner
from src.paper_archive import load_protocol
from src.preservation import read_record
from src.scanner_outcomes import benchmark_values


@pytest.mark.parametrize("now,session,state,eligible", [
    ("2026-10-06T11:00:00Z", "2026-10-05", "closed", "2026-10-05"),
    ("2026-10-06T13:30:00Z", "2026-10-05", "open", None),
    ("2026-10-06T19:59:00Z", "2026-10-05", "open", None),
    ("2026-10-06T20:00:00Z", "2026-10-06", "closed", None),
    ("2026-10-07T04:15:00Z", "2026-10-06", "closed", "2026-10-06"),
    ("2026-11-27T18:00:00Z", "2026-11-27", "closed", None),
    ("2026-12-25T12:00:00Z", "2026-12-24", "closed", "2026-12-24"),
])
def test_completed_session_excludes_open_bar(now, session, state, eligible):
    result = scanner.market_clock(now)
    assert result["latest_completed_session"] == session
    assert result["market_state"].startswith(state)
    assert result["eligible_session"] == eligible


def test_athens_dst_is_timezone_aware():
    summer = pd.Timestamp(scanner.market_clock("2026-10-06T11:00:00Z")["next_market_open"]).tz_convert("Europe/Athens")
    winter = pd.Timestamp(scanner.market_clock("2026-11-03T11:00:00Z")["next_market_open"]).tz_convert("Europe/Athens")
    assert summer.hour == winter.hour == 16
    assert summer.utcoffset() != winter.utcoffset()


def test_cash_uses_elapsed_calendar_days_and_year_boundaries():
    assert scanner.cash_return(.05, "2026-10-06", "2026-10-06") == 0
    assert scanner.cash_return(.05, "2026-10-09", "2026-10-12") == pytest.approx(.05*3/365)
    assert scanner.cash_return(.05, "2023-12-31", "2024-01-02") == pytest.approx(.05*(1/365+1/366))
    scenarios = scanner.cash_scenarios(.05, "2026-10-05")
    ten = next(r for r in scenarios if r["horizon"] == 10)
    assert ten["return"] == pytest.approx(.05*(pd.Timestamp(ten["exit_session"])-pd.Timestamp(ten["entry_session"])).days/365)


@pytest.mark.parametrize("rate,start,end", [(float('nan'), '2026-01-01', '2026-01-02'),
                                           (.05, '2026-01-02', '2026-01-01'),
                                           (-.01, '2026-01-01', '2026-01-02')])
def test_invalid_cash_inputs_fail(rate, start, end):
    with pytest.raises(ValueError):
        scanner.cash_return(rate, start, end)


def xml_rates(date="2026-10-05", rate="4.0"):
    return f'<feed xmlns:d="urn:fields"><entry><properties><d:QUOTE_DATE>{date}T00:00:00</d:QUOTE_DATE><d:ROUND_B1_YIELD_13WK_2>{rate}</d:ROUND_B1_YIELD_13WK_2><d:ROUND_B1_CLOSE_13WK_2>99</d:ROUND_B1_CLOSE_13WK_2></properties></entry></feed>'.encode()


def test_treasury_uses_investment_yield_not_discount():
    quote = scanner.parse_treasury(xml_rates(), "2026-10-05")
    assert quote["annual_yield"] == .04
    with pytest.raises(ValueError, match="No decision-date"):
        scanner.parse_treasury(xml_rates("2026-10-06"), "2026-10-05")
    with pytest.raises(ValueError, match="stale"):
        scanner.parse_treasury(xml_rates("2026-09-01"), "2026-10-05")
    with pytest.raises(ValueError):
        scanner.parse_treasury(xml_rates(rate="NaN"), "2026-10-05")


def test_treasury_network_failure_is_explicit(tmp_path, monkeypatch):
    def fail(*a, **kw):
        raise OSError("network unavailable")
    monkeypatch.setattr(scanner, "urlopen", fail)
    result = scanner.treasury_quote(tmp_path, "2026-10-05")
    assert result["status"] == "unavailable" and result["annual_yield"] is None
    assert "network unavailable" in result["error"]


def test_exact_95_requested_names_preserved_on_total_failure():
    result = scanner.scan_frames({}, {}, "2026-10-05")
    assert [r["ticker"] for r in result["rows"]] == load_protocol()["universe"]
    assert len(result["rows"]) == 95
    assert all(r["status"] == "unavailable" and r["error"] for r in result["rows"])


def test_deterministic_scanner_and_future_bars_never_change_decision(monkeypatch):
    config = load_protocol()
    config["universe"] = ["ABT"]
    monkeypatch.setattr(scanner, "load_protocol", lambda: deepcopy(config))
    frames = {t: prices(t, end="2026-10-19", periods=650) for t in ["ABT", "SPY"]}
    first = scanner.scan_frames(frames, {}, "2026-10-05")
    assert first == scanner.scan_frames(frames, {}, "2026-10-05")
    for frame in frames.values():
        frame.loc[frame.timestamp.gt("2026-10-05"), ["open", "high", "low", "close"]] *= 20
    assert first == scanner.scan_frames(frames, {}, "2026-10-05")
    from src.features import build_features
    from src.signals import build_signals
    prefix = {t: f.loc[f.timestamp.le("2026-10-05")].copy() for t, f in frames.items()}
    expected = build_signals(build_features(prefix["ABT"], benchmark=prefix["SPY"]), **config["signal_parameters"]).iloc[-1]
    assert first["rows"][0]["features"]["dip_event_v1"] == bool(expected.dip_event_v1)


def test_reference_ceiling_excludes_current_outcome_and_accumulating_holdout():
    from src.features import build_features
    from src.signals import build_signals
    frames = {t: prices(t, end="2026-11-02", periods=900) for t in ["ABT", "SPY"]}
    signal = build_signals(build_features(frames["ABT"], benchmark=frames["SPY"]))
    first, table, _ = scanner.reference_tables(signal, frames["SPY"], "2026-10-06")
    assert table.loc[table.status.eq("completed"), "end_timestamp"].max() < pd.Timestamp("2026-10-05")
    signal.loc[signal.timestamp.ge("2026-10-05"), ["open", "high", "low", "close"]] *= 50
    second, _, _ = scanner.reference_tables(signal, frames["SPY"], "2026-10-20")
    assert first == second


def test_partial_coverage_and_stale_data_are_visible(monkeypatch):
    config = load_protocol()
    config["universe"] = ["ABT", "BMY"]
    monkeypatch.setattr(scanner, "load_protocol", lambda: deepcopy(config))
    frames = {"ABT": prices(end="2026-10-02"), "SPY": prices("SPY")}
    rows = scanner.scan_frames(frames, {"BMY": {"error": "Malformed OHLC"}}, "2026-10-05")["rows"]
    assert rows[0]["status"] == "stale"
    assert rows[1]["status"] == "unavailable" and rows[1]["error"] == "Malformed OHLC"


def test_status_and_snapshot_preserve_decisions_and_duplicate_identity(enrolled, monkeypatch):
    root, _, config = enrolled
    monkeypatch.setattr(scanner, "load_protocol", lambda: deepcopy(config))
    before = (root/"runs/test/result.json").read_bytes()
    status = scanner.collection_status(root, "test")
    assert status["expected_tickers"] == status["successful_tickers"] == 2
    assert status["completion_status"] == "complete"
    one = scanner.build_today(root, "test", {"status": "unavailable", "annual_yield": None, "error": "No quote"})
    two = scanner.build_today(root, "test", {"status": "unavailable", "annual_yield": None})
    assert one == two
    assert (root/"runs/test/result.json").read_bytes() == before
    assert scanner.verify_today(root, "test") == one


def test_interrupted_collection_has_no_successful_status(enrolled):
    root, _, _ = enrolled
    (root/"runs/test/receipt.json").unlink()
    status = scanner.collection_status(root, "test")
    assert status["completion_status"] == "interrupted" and status["collection_completed"] is None


def test_separate_benchmark_pending_and_actual_cash_endpoints():
    stock = prices("ABT", end="2026-10-06", periods=2)
    spy = stock.assign(ticker="SPY")
    quote = {"annual_yield": .05, "prospective_eligible": True}
    rows = benchmark_values(stock, spy, "2026-10-05", {"dip_component_count": 3}, quote, "2026-10-07T05:00:00Z")
    one = next(r for r in rows if r["horizon"] == 1)
    assert one["cash"] == 0 and one["net"] < one["gross"]
    assert next(r for r in rows if r["horizon"] == 10)["cash"] is None
    late = benchmark_values(stock, spy, "2026-10-05", {"dip_component_count": 3}, quote | {"prospective_eligible": False}, "2026-10-07T05:00:00Z")
    assert late[0]["cash"] is None
    with pytest.raises(ValueError, match="Incomplete/future"):
        benchmark_values(stock, spy, "2026-10-05", {"dip_component_count": 3}, quote, "2026-10-06T19:00:00Z")


def test_latest_pointer_publication_is_atomic(tmp_path, monkeypatch):
    path = tmp_path/"latest.json"
    scanner.publish_pointer(path, {"version": 1})
    def fail(*a):
        raise OSError("interrupted replacement")
    monkeypatch.setattr(scanner.os, "replace", fail)
    with pytest.raises(OSError):
        scanner.publish_pointer(path, {"version": 2})
    assert path.read_bytes() == b'{"version":1}\n'
    assert not list(tmp_path.glob(".latest-*"))


def test_transient_windows_sharing_failure_keeps_atomic_pointer(tmp_path, monkeypatch):
    from src import atomic_pointer
    path = tmp_path/"latest.json"
    scanner.publish_pointer(path, {"version": 1})
    original = atomic_pointer.os.replace
    calls = []
    def busy(source, target):
        calls.append(1)
        if len(calls) < 3:
            assert path.read_bytes() == b'{"version":1}\n'
            raise PermissionError("Windows sharing violation")
        original(source,target)
    monkeypatch.setattr(atomic_pointer.os, "replace", busy)
    monkeypatch.setattr(atomic_pointer.time, "sleep", lambda _: None)
    scanner.publish_pointer(path, {"version": 2})
    assert len(calls) == 3 and path.read_bytes() == b'{"version":2}\n'


def test_transient_retries_retained_and_invalid_ohlc_not_retried(tmp_path, monkeypatch):
    from scripts import archive_signals
    config = {"benchmark": "SPY", "universe": ["ABT"]}
    monkeypatch.setattr(archive_signals, "load_protocol", lambda: config)
    monkeypatch.setattr(archive_signals, "code_identity", lambda: {})
    monkeypatch.setattr(archive_signals, "begin_run", lambda *a, **kw: {"universe": ["ABT"]})
    monkeypatch.setattr(archive_signals, "finish_run", lambda *a, **kw: None)
    monkeypatch.setattr(archive_signals, "verify_run", lambda *a, **kw: {"status": "partial"})
    monkeypatch.setattr(archive_signals.time, "sleep", lambda _: None)
    attempts = {"SPY": 0, "ABT": 0}
    def capture(root, ticker, **kw):
        attempts[ticker] += 1
        if ticker == "SPY" and attempts[ticker] == 1:
            return {"ticker": ticker, "status": "unavailable", "error": "RuntimeError: Network failure"}
        if ticker == "ABT":
            return {"ticker": ticker, "status": "unavailable", "error": "ValueError: Invalid OHLC"}
        return {"ticker": ticker, "status": "available", "error": None}
    monkeypatch.setattr(archive_signals, "capture_input", capture)
    assert archive_signals.collect(tmp_path, session="2026-10-05", run_id="test")["status"] == "partial"
    assert attempts == {"SPY": 2, "ABT": 1}
    assert read_record(tmp_path/"runs/test/attempts/SPY/attempt-1.json")["status"] == "unavailable"


def test_benchmark_review_refuses_early_unblinding(tmp_path):
    from src.scanner_outcomes import benchmark_review
    with pytest.raises(ValueError, match="locked"):
        benchmark_review(tmp_path, {"scheduled_sessions": 100, "complete_runs": 100}, "2026-10-06T12:00:00Z")
    assert not (tmp_path/"exp005/benchmark_reviews").exists()


def test_sealed_partial_run_shows_next_new_collection_window(tmp_path):
    from src.preservation import write_record, canonical_json, digest
    root = tmp_path/"data/archive"
    payload = {"session": "2026-10-05", "status": {"collection_completed": "2026-10-06T11:00:00Z"}}
    write_record(root/"today/test.json", payload)
    scanner.publish_pointer(tmp_path/"data/current_market/latest.json", {"root": "data/archive", "run_id": "test", "sha256": digest(canonical_json(payload))})
    exported = scanner.export_today(tmp_path, "2026-10-06T12:00:00Z")
    assert exported["clock"]["collection_window_start"] == "2026-10-07T04:15:00+00:00"
    assert exported["clock"]["eligible_session"] == "2026-10-05"


def test_benchmark_attachment_is_separate_immutable_and_reproducible(enrolled, monkeypatch, tmp_path):
    from src import scanner_outcomes as benchmarks
    from src import paper_archive as archive
    from src.data import PROVENANCE_KEY, save_parquet
    root, _, config = enrolled
    monkeypatch.setattr(benchmarks, "load_protocol", lambda: deepcopy(config))
    monkeypatch.setattr(benchmarks, "market_clock", lambda _: {"latest_completed_session": "2026-10-06"})
    monkeypatch.setattr(benchmarks, "utc_now", lambda: "2026-10-07T06:00:00Z")
    acquired = {}
    for t in ["ABT", "BMY", "SPY"]:
        f = prices(t, end="2026-10-06", periods=301)
        f = f.loc[f.timestamp.ge("2026-10-05")].copy()
        f.attrs[PROVENANCE_KEY] = dict(schema_version=1, provider="yfinance", ticker=t,
            interval="1d", retrieved_at="2026-10-07T05:00:00Z", requested_start="2016-09-29",
            requested_end="2026-10-07", adjustment="auto_adjust=True; provider-reported volume")
        save_parquet(f, tmp_path/"new"/(t+".parquet"))
        acquired[t] = archive.capture_input(root,t,config=config,session="2026-10-06",replay_cache=tmp_path/"new")
        acquired[t]["input_kind"] = "new_provider_vintage"
    monkeypatch.setattr(benchmarks, "capture_input", lambda root,t,**kw: acquired[t])
    before = (root/"runs/test/result.json").read_bytes()
    assert benchmarks.attach_benchmarks(root)["attached_benchmark_vintages"] == 2
    paths = list((root/"exp005/benchmarks").glob("*/*/*.json"))
    saved = {p:p.read_bytes() for p in paths}
    assert benchmarks.attach_benchmarks(root)["attached_benchmark_vintages"] == 0
    for p in paths:
        record = benchmarks.verify_benchmark(root,p)
        assert record["selection"] == "event"
        assert record["forward"][0]["cash"] is None  # no decision-linked quote
        assert p.read_bytes() == saved[p]
    assert (root/"runs/test/result.json").read_bytes() == before
