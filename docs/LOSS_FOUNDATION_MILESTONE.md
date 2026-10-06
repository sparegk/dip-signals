# Data quality and loss research milestone — 2026-10-06

**New diagnostic data passes 95/95; old prospective coverage remains 72/95.**
The numerical mechanism now has paired evidence and a narrow, auditable fix.
Independent candle prices and complete historical identity continuity remain
unverified. Losing trades do not have a demonstrated stable entry predictor;
no new stop, filter or optimized risk model was selected.

1. **All 23 failures:** ABBV, ABT, AMT, BAC, CMCSA, DUK, GM, IBM, KO, LMT, MDT,
   MMM, MO, MRK, NEE, PFE, PG, PM, T, TXN, VZ, WFC and XOM. Each independently
   classified as a one-spacing adjusted-close boundary defect. No missing/stale,
   open-range or inverted high/low defect explains these original rejections.
2. **Exact observations:** 41 original candles, with session, OHLC, failed rule,
   discrepancy, raw references and new paired operands in the expandable tables
   in [DATA_QUALITY_AUDIT.md](DATA_QUALITY_AUDIT.md). Original error:
   `Malformed OHLC: open/close must lie within low/high`.
3. **Adjustment arithmetic:** yfinance scales O/H/L by Adj Close / Close but
   copies adjusted close directly. New paired inputs reproduce 30 one-step errors;
   all 41 original dates have corresponding exact raw boundary ties in the new
   vintage. Original unadjusted factors were not retained and cannot be proven.
4. **Identity:** retained official SEC ticker/exchange mapping and all 23 issuer
   submissions confirm current associations. CMCSA's listed Class A is distinct
   from unlisted Class B. IBM, MMM, MRK and T have documented spin-off boundaries;
   XOM's July 2026 Holdings redomiciliation changes its CIK. Historical security
   master, ticker reuse and full share-class continuity remain incomplete.
5. **Independent comparison:** all Stooq requests returned browser challenges.
   An initial Nasdaq date-range error and corrected zero-record response are
   retained. No independent candle agreement is claimed. No credentials, purchases,
   challenge bypass or substitute Yahoo mirror was used.
6. **Fix justified:** paired mathematical evidence supports preserving exact
   boundary equality during adjustment. It does not justify a generic tolerance
   or establish original corporate-action factors or price accuracy.
7. **Exact change:** `raw-boundary-equality-v1`, effective October 6 signal session.
   Strictly validate paired raw OHLC; use the existing adjustment calculation;
   reconcile only an exact raw close/high or close/low tie producing one adjacent
   float. Record before/after operands, factor and reason. Close and every previously
   valid row remain unchanged. Retain paired, transformed and validated hashes and
   verify the complete linkage. Legacy ingestion/cache validation stays strict.
8. **Coverage:** original immutable October 5 run remains 72/95 (75.79%) partial.
   New diagnostic vintages pass 95/95 plus SPY: 77 of 96 responses already pass;
   19 require 37 recorded transformations. Diagnostic success is not enrollment.
9. **Coverage gate:** a complete future run is now technically possible with the
   checked inputs, but sustained timely availability is unproven. Gate remains
   at least 100 scheduled sessions and 80% complete timely original runs, each
   covering all 95. Registered review dates remain April/October 2027. Not passed.
10. **Recurring patterns:** the current original run retains all 23 failures;
    older EXP-003 vintages show the same sparse boundary pattern but are diagnostic
    vintages, not additional daily prospective sessions. Today adds session counts,
    categories, recurring names and a descriptive valid-session streak. Interrupted
    acquisition and evaluated decisions are separate; no ticker leaves the denominator.
11. **Historical losses:** hash-verified consumed EXP-002 data gives 4,652 completed
    independent control trades: 2,432 positive net and 2,220 nonpositive net.
    Entry ATR, drawdown, z-score, relative weakness and volume distributions overlap.
    Median ATR/close is 2.638% versus 2.636%; prior-dip spacing median is ten bars
    in both groups. Several median differences change sign across annual folds.
12. **MAE:** full ten-bar median signed MAE is -1.679% for control winners versus
    -6.301% for losses. Loss signed p10/p25/p50/p75/p90:
    -12.976% / -9.119% / -6.301% / -4.023% / -2.612%.
    These are future outcomes, not predictors; through-exit MAE is kept separate.
13. **ATR normalization:** median adverse magnitude / entry-known ATR fraction
    is 0.642 for control winners versus 2.277 for losses. Loss percentiles:
    1.078 / 1.586 / 2.277 / 3.138 / 4.287. Normalization reduces association with
    ATR but does not remove subgroup differences or establish an acceptable stop.
14. **Stop/recovery:** inspect only the already frozen historical 7% control.
    Of 902 stopped trades with full twenty-bar paths, 367 (40.69%) subsequently
    close above original entry after costs; conditional median recovery is bar 11.
    Same-exit-session recovery is excluded; non-recoveries stay in the denominator.
    This diagnoses lost rebound opportunities without searching a stop grid.
15. **Gaps:** 143/952 stop exits (15.02%) fill at a gap-through open. Stops cannot
    guarantee the barrier loss. Overnight open/prior-close and intraday low/open
    moves are separate, overlapping diagnostics. Daily bars lack intraday order.
16. **Regimes:** causal SPY above/below SMA200 loss frequencies are similar,
    approximately 47.9%/47.2%; average losses differ, approximately -4.19%/-5.74%.
    Stress affects severity; no regime filter is validated.
17. **Entry predictability:** no stable predictor has been demonstrated. Covariate
    overlap and fold variation limit inference. No classifier was fitted and no
    prospective returns were inspected. Future MAE separation is not entry evidence.
18. **Problem attribution:** mixed/unclear. Entry-quality improvement is unproven;
    rebound duration and exit path differences are plausible research directions;
    gaps/regime stress also contribute. A stable entry predictor may not exist.
    Stronger evidence is needed before deploying a flexible risk model.
19. **Future hypotheses:** ATR-conditioned MAE/MFE envelope, recovery duration with
    censoring, gap/regime portfolio stress, then entry-quality covariates if stable
    training evidence emerges. Requirements and joint EV/downside/capture objectives
    are in [RISK_MANAGEMENT_RESEARCH.md](RISK_MANAGEMENT_RESEARCH.md). No policy implemented.
20. **Do not optimize yet:** stop/target percentages, V1 thresholds, component
    filters, rankings, universe, entry delay or position sizing. Consumed folds are
    not fresh OOS. Train-only calibration, advance freezing, cross-sectional and
    chronological tests are necessary; EXP-005 remains sealed validation data.
21. **Prospective archive:** three genuine events (C, GE, HD), 69 non-events,
    23 excluded names, three pending events; **zero genuine prospective outcomes**.
    Original decisions, all failure attempts and experiment outputs stay unchanged.
    All 654 preserved files passed a byte-hash inventory check. Current intraday
    October 6 bars are excluded; latest completed session remains October 5.
22. **Checks:** 677 backend tests, 22 frontend tests, five browser scenarios,
    production build, formatting, pip check, retained-data audit, original EXP-003
    documentation check and prospective archive verification passed. Diagnostic
    reruns are immutable/idempotent. Generated data remains ignored.
23. **Git:** implementation, evidence, tests and documentation are one coherent
    milestone; the final commit/push identity is reported with delivery. No artificial
    contribution commits. Protocol amendment precedes October 6 session eligibility.
24. **Next milestone:** sustained timely original 95/95 collection and accessible
    independent candle/security-master validation. A separately registered training-
    only risk-envelope investigation can follow reliable foundations; no automatic
    optimization starts. Fresh edge evidence still requires the existing review gates.

Daily operation from a clean committed revision:

```powershell
.\.venv\Scripts\python.exe -W error -m scripts.run_today
.\.venv\Scripts\python.exe -W error -m scripts.update_prospective_outcomes
.\.venv\Scripts\python.exe -W error -m scripts.verify_prospective
```

Next collection: **October 7, 07:15–16:30 Athens**, for the October 6 completed
session. Future windows use timezone-aware calendar rules, not fixed DST offsets.
Today shows freshness, all-name health, missing/failing reasons, current V1 events
and historical risk context. A saved snapshot is not an auto-updating feed.
Collection remains manual; run the daily command in its registered window.
