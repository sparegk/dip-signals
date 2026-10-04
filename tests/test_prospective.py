"""Offline EXP-005 timing, causal context and immutable paired outcome contracts."""

from copy import deepcopy
import json

import numpy as np
import pandas as pd
import pytest

from src import paper_archive as archive
from src import prospective as prospective
from src import archive_context as context
from src import prospective_outcomes as outcomes
from src.data import PROVENANCE_KEY, save_parquet
from src.preservation import read_record, write_record


def prices(ticker="ABT", end="2026-10-05", periods=300):
    dates = pd.bdate_range(end=end, periods=periods).astype("datetime64[ns]")
    p = 100 + np.arange(periods)*.03 + np.sin(np.arange(periods)/5)
    return pd.DataFrame(dict(timestamp=dates, ticker=ticker, open=p, high=p+1, low=p-1,
                             close=p, volume=np.full(periods,100,dtype=np.int64)))


@pytest.mark.parametrize("now", ["2026-10-06T04:15:00Z", "2026-10-06T13:29:59Z"])
def test_current_session_only(now):
    assert prospective.eligible_session(now) == "2026-10-05"
    with pytest.raises(ValueError, match="backfill"):
        prospective.eligible_session(now, "2025-01-10")


@pytest.mark.parametrize("now", ["2026-10-05T19:59:00Z", "2026-10-06T04:14:59Z",
                                  "2026-10-06T13:30:00Z", "2026-10-04T12:00:00Z"])
def test_timing_and_effective_date_fail_closed(now):
    with pytest.raises(ValueError):
        prospective.eligible_session(now)


def test_holiday_and_dst_collection_windows():
    assert prospective.eligible_session("2026-11-28T06:00:00Z") == "2026-11-27"
    assert prospective.eligible_session("2026-12-26T06:00:00Z") == "2026-12-24"


def test_volatility_uses_prior_only_and_is_ticker_local():
    stock, spy = prices(), prices("SPY")
    first = prospective.volatility_context(stock, spy, "2026-09-25")
    stock.loc[stock.timestamp.gt("2026-09-25"), ["open","high","low","close"]] *= 10
    spy.loc[spy.timestamp.gt("2026-09-25"), ["open","high","low","close"]] *= 10
    assert prospective.volatility_context(stock, spy, "2026-09-25") == first
    assert first["group"] in {"low","middle","high"}
    assert first["prior_valid_observations"] == 252
    short = prospective.volatility_context(prices(periods=40), prices("SPY",periods=40), "2026-10-05")
    assert short["group"] == "unavailable"


@pytest.fixture
def enrolled(tmp_path, monkeypatch):
    config = archive.load_protocol(); config["universe"] = ["ABT", "BMY"]
    monkeypatch.setattr(archive, "load_protocol", lambda:deepcopy(config))
    monkeypatch.setattr(prospective, "load_protocol", lambda:deepcopy(config))
    monkeypatch.setattr(outcomes, "load_protocol", lambda:deepcopy(config))
    monkeypatch.setattr(context, "code_identity", lambda:{"revision":"test","dirty":False,"source_sha256":{}})
    root = tmp_path / "archive"
    frames = {}
    for ticker in ["ABT", "BMY", "SPY"]:
        frame = prices(ticker)
        if ticker != "SPY":
            frame.loc[299, ["open", "high", "low", "close"]] = [60.,61.,59.,60.]
        frame.attrs[PROVENANCE_KEY] = dict(schema_version=1, provider="yfinance", ticker=ticker,
            interval="1d", retrieved_at="2026-10-06T11:00:00Z", requested_start="2016-09-29",
            requested_end="2026-10-06", adjustment="auto_adjust=True; provider-reported volume")
        save_parquet(frame, tmp_path/"cache"/(ticker+".parquet")); frames[ticker] = frame
    inputs = {t:archive.capture_input(root,t,config=config,session="2026-10-05",replay_cache=tmp_path/"cache") for t in frames}
    for item in inputs.values(): item["input_kind"] = "new_provider_vintage"
    intent = archive.begin_run(root,"test",session="2026-10-05",mode="collect",config=config,
                              code={"revision":"test","dirty":False},clock=lambda:"2026-10-06T10:00:00Z")
    archive.finish_run(root,intent,inputs,clock=lambda:"2026-10-06T12:00:00Z")
    prospective.enroll(root,"test",clock=lambda:"2026-10-06T12:10:00Z")
    return root, frames, config


def test_enrollment_replays_and_retry_does_not_duplicate(enrolled):
    root, _, _ = enrolled
    before = (root/"runs/test/result.json").read_bytes()
    first = prospective.verify_enrollment(root,"test")
    assert set(first["receipt"]["classifications"].values()) == {"prospective"}
    assert prospective.enroll(root,"test",clock=lambda:pytest.fail("No retry clock")) == first
    assert (root/"runs/test/result.json").read_bytes() == before
    assert set(first["decision"]) & {"forward_return", "outcomes", "entry_price"} == set()


def test_future_fields_and_conflicts_rejected(enrolled):
    root, _, _ = enrolled
    path = root/"exp005/decisions/test.json"
    payload = read_record(path)
    with pytest.raises(ValueError, match="Conflicting"):
        write_record(path, payload | {"future_return":.5})
    path.unlink(); write_record(path,payload | {"future_return":.5})
    with pytest.raises(ValueError, match="schema"):
        prospective.verify_enrollment(root,"test")


def test_interrupted_enrollment_cannot_be_resealed(enrolled):
    root, _, _ = enrolled
    (root/"exp005/receipts/test.json").unlink()
    with pytest.raises(FileNotFoundError):
        prospective.enroll(root,"test")
    summary = prospective.operational_summary(root,as_of="2026-10-06T14:00:00Z")
    assert summary["genuine_records"] == 0
    assert summary["failed_collections"] == 1
    assert summary["incomplete_runs"][0]["status"] == "interrupted_enrollment"


def test_zero_evidence_and_pending_summary(enrolled):
    root, _, _ = enrolled
    summary = prospective.operational_summary(root,as_of="2026-10-06T12:00:00Z")
    assert summary["genuine_records"] == 2
    assert summary["completed_outcomes"] == 0
    assert summary["comparison"] == []
    assert summary["performance_status"] == "sealed_until_registered_review"


def path(periods):
    frame = prices(end="2026-10-19",periods=periods)
    frame.loc[:, ["open","close"]] = 100.
    frame.loc[:, "high"] = 111.
    frame.loc[:, "low"] = 92.
    return frame


def test_paired_policies_use_same_entry_stop_first_and_costs():
    stock = path(11); spy = stock.assign(ticker="SPY")
    result = outcomes.event_outcomes(stock,spy,session=stock.timestamp.iloc[0].date().isoformat(),
                                    component_count=3,available_at="2026-10-20T12:00:00Z")
    fixed = result["policies"]["historical_v1_control"][0]
    hold = result["policies"]["ten_bar_hold"][0]
    assert result["paired_complete"]
    assert fixed["entry_price"] == hold["entry_price"] == 100
    assert fixed["exit_reason"] == "stop_loss"
    assert hold["exit_reason"] == "time_exit"
    assert fixed["net_return"] < -.07
    assert hold["net_return"] < 0
    assert [r["status"] for r in result["forward"]] == ["completed"]*4+["incomplete_window"]


def test_incomplete_window_does_not_score_early_barrier():
    stock = path(4)
    result = outcomes.event_outcomes(stock,stock.assign(ticker="SPY"),
        session=stock.timestamp.iloc[0].date().isoformat(),component_count=3,available_at="2026-10-20T12:00:00Z")
    assert not result["paired_complete"]
    assert result["policies"]["historical_v1_control"][0]["status"] == "incomplete_window"


def test_outcomes_refuse_uncompleted_bars():
    stock = path(4)
    with pytest.raises(ValueError,match="incomplete/future"):
        outcomes.event_outcomes(stock,stock.assign(ticker="SPY"),session=stock.timestamp.iloc[0].date().isoformat(),
                                component_count=3,available_at="2026-10-19T19:00:00Z")


def test_review_requires_exact_date_and_original_all_name_coverage():
    summary = {"scheduled_sessions":110,"complete_runs":100}
    assert outcomes.review_allowed(summary,now="2027-04-01T12:00:00Z")
    assert not outcomes.review_allowed(summary,now="2027-03-31T12:00:00Z")
    assert not outcomes.review_allowed(summary,now="2027-04-02T12:00:00Z")
    assert not outcomes.review_allowed(summary | {"complete_runs":70},now="2027-04-01T12:00:00Z")


def test_frozen_protocol_and_95_names():
    rules = prospective.protocol()
    assert len(archive.load_protocol()["universe"]) == 95
    assert rules["horizons"] == [1,3,5,10,20]
    assert rules["policies"]["ten_bar_hold"]["stop_loss"] is None


def test_attached_outcomes_preserve_decisions_and_require_versions(enrolled, tmp_path):
    root, _, config = enrolled
    before = (root/"runs/test/result.json").read_bytes()
    before_enrollment = (root/"exp005/decisions/test.json").read_bytes()
    inputs = {}
    for ticker in ("ABT","SPY"):
        frame = prices(ticker,end="2026-11-02",periods=21)
        frame.attrs[PROVENANCE_KEY] = dict(schema_version=1,provider="yfinance",ticker=ticker,interval="1d",
            retrieved_at="2026-11-03T11:00:00Z",requested_start="2016-09-29",requested_end="2026-11-03",
            adjustment="auto_adjust=True; provider-reported volume")
        save_parquet(frame,tmp_path/"future"/(ticker+".parquet"))
        inputs[ticker] = archive.capture_input(root,ticker,config=config,session="2026-11-02",replay_cache=tmp_path/"future")
        inputs[ticker]["input_kind"] = "new_provider_vintage"
    first = outcomes.attach_outcome(root,"test","ABT",inputs,version="2026-11-02",clock=lambda:"2026-11-03T12:00:00Z")
    assert first["paired_complete"]
    assert outcomes.attach_outcome(root,"test","ABT",inputs,version="2026-11-02",clock=lambda:pytest.fail("Retry clock")) == first
    assert (root/"runs/test/result.json").read_bytes() == before
    assert (root/"exp005/decisions/test.json").read_bytes() == before_enrollment
    with pytest.raises(ValueError,match="requires parent"):
        outcomes.attach_outcome(root,"test","ABT",inputs,version="next")
    second = outcomes.attach_outcome(root,"test","ABT",inputs,version="next",corrects="2026-11-02",
                                    reason="New vintage",clock=lambda:"2026-11-03T12:01:00Z")
    assert second["corrects"] == first["version"]
    assert len(outcomes.verified_outcomes(root)) == 1


def test_replay_and_pre_protocol_runs_cannot_enroll(enrolled):
    root, _, config = enrolled
    source = read_record(root/"runs/test/result.json")
    import shutil
    replay_root = root.parent/"replay_archive"
    shutil.copytree(root/"objects",replay_root/"objects")
    intent = archive.begin_run(replay_root,"replay",session="2026-10-05",mode="replay",config=config,
                              code={"revision":"test","dirty":False},clock=lambda:"2026-10-06T12:00:00Z")
    archive.finish_run(replay_root,intent,source["inputs"],clock=lambda:"2026-10-06T12:00:01Z")
    with pytest.raises(ValueError,match="Replay"):
        prospective.enroll(replay_root,"replay",clock=lambda:"2026-10-06T12:10:00Z")
    assert prospective.operational_summary(root,as_of="2026-10-06T14:00:00Z")["events"] == 2
    with pytest.raises(ValueError,match="backfill"):
        prospective.eligible_session("2026-10-06T12:00:00Z","2026-09-28")


def test_no_review_can_be_opened_by_a_future_export_cutoff(tmp_path):
    future = prospective.operational_summary(tmp_path,as_of="2027-04-01T12:00:00Z")
    assert future["comparison"] == []
    with pytest.raises(ValueError,match="locked"):
        outcomes.review_report(tmp_path,clock=lambda:"2027-04-01T12:00:00Z")


def test_registered_report_pipeline_uses_same_event_and_cannot_peek(enrolled, monkeypatch, tmp_path):
    # Synthetic mature outcomes only; this never touches the genuine archive.
    root, _, _ = enrolled
    stock = path(11)
    event = outcomes.event_outcomes(stock,stock.assign(ticker="SPY"),session=stock.timestamp.iloc[0].date().isoformat(),
                                   component_count=3,available_at="2026-10-20T12:00:00Z")
    record = {"record_id":"test:ABT","volatility":{"group":"low"},"session":"2026-10-05"}
    summary = {"scheduled_sessions":110,"complete_runs":100,"records":[record],"completed_outcomes":1}
    monkeypatch.setattr(prospective,"operational_summary",lambda *a,**kw:summary)
    monkeypatch.setattr(outcomes,"verified_outcomes",lambda *a:[event | {"run_id":"test","ticker":"ABT"}])
    with pytest.raises(ValueError,match="locked"):
        outcomes.review_report(root,clock=lambda:"2027-03-31T12:00:00Z")
    report = outcomes.review_report(root,clock=lambda:"2027-04-01T12:00:00Z")
    assert report["completed_events"] == 1
    all_rows = [r for r in report["comparison"] if r["grouping"] == "all"]
    assert len(all_rows) == 2
    assert all(r["trade_count"] == 1 for r in all_rows)
    assert report["milestones_crossed"] == []
