# EXP-005 daily workstation completion report

The system collects and displays completed-session paper research. The first
collection is **partial: 72/95 evaluated, 23 failed**. Three genuine V1 events were
recorded for 2026-10-05: **C, GE and HD**. There are **zero genuine prospective
outcome records**, zero benchmark outcome records and three pending events.
No prospective profitability or edge has been established.

## 1. Protocol

`EXP005_PROTOCOL.md` is EXP-005 — Prospective Market Scanner & Validation. The
original configuration/hash, 95 names, V1, effective session, exits, volatility
tertiles and review gates remain frozen. `4925d8b` registered the additive protocol
before collection. The official Treasury URL/schema correction was committed with
implementation before enrollment; benchmark methodology was unchanged.

## 2–3. Architecture and Today

`scripts/run_today.py` determines the real XNYS completed session and collection
window, uses the frozen collector/V1 APIs, enrolls only when timely, retains
immutable Today/status sidecars, and atomically selects a browser generation.
Outside-window snapshots use a separate archive and never become enrollment.
Intraday context is explicitly unavailable. Python owns all calculations.

Today is default. Navigation starts Today, Signals, Edge, Experiments, Robustness,
Backtest, Features, Paper Archive, Data Quality, Research Diagnosis, Hypotheses and
Roadmap. Existing views remain accessible. Today shows Athens session/timing/status,
candidates/details, universe health, SPY context, optional 0/4–4/4 monitor and archive
progress. Tables sort individual quantities; no combined score is added.

## 4–7. Current session, coverage and candidate statistics

The actual 2026-10-06 clock selected **2026-10-05** before October 6's open.
Original publication was **14:19:57 Athens**; enrollment was sealed before
**16:30 Athens**. The run retains 72 prospective decisions, three events,
69 non-events and 23 excluded records. It does not satisfy the all-name coverage
gate. SPY close: 774.83; daily return: +0.674%; ATR/close: 0.872%; above SMA200.

Prices are provider-adjusted, not entry fills. References finish before 2026-10-05.

| Ticker | Close | Components | 60-bar drawdown | Z-score | ATR/close | Prior control N | Historical V1 net EV | Prior 10-bar gross mean | Prior 10-bar SPY excess |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C | 128.55 | 3/4 | -8.177% | -1.333 | 2.452% | 104 | +1.288% | +1.439% | +0.280 pp |
| GE | 306.34 | 3/4 | -19.520% | -1.557 | 2.675% | 118 | -0.029% | +0.486% | +0.041 pp |
| HD | 281.15 | 3/4 | -20.358% | -1.588 | 2.304% | 107 | -0.972% | -0.824% | -0.605 pp |

C activates z-score, low proximity and relative weakness. GE and HD activate
drawdown, z-score and low proximity. All are unchanged V1 rising edges. No signal
is removed because its historical EV is negative.

## 8. Historical reference EV

Truncate before both the signal and 2026-10-05; every forward window must finish
before that cutoff. At least 20 completed same-ticker events are required **per
horizon**, otherwise show insufficient history. Net EV uses the historical V1
barrier engine, full ten-bar maturity, 1 bp commission and 5 bp slippage per side.
Same-ticker and cross-sectional references remain separate. The current broader
reference is +0.498% net across 7,371 mature events in 72 available requested names.
This new descriptive vintage does not replace EXP-002's 74-name evaluation or its
conclusions. Survivor selection, provider exclusions, overlap and adjusted revisions
remain limitations; historical means are not forecasts.

## 9–10. SPY and cash/Treasury opportunity cost

SPY open/close use the stock's exact entry/end sessions; report paired excess and
paired N. Ready non-condition days and all ready stock days are distinct controls
at 1/3/5/10/20 observed bars. Unpaired stock-control differences are descriptive,
not causal effects. Prospective control vintages are separately retained.

The official retained 13-week investment yield dated 2026-10-05 is **4.15%
annualized**, retrieved before entry. Expected October 6–19 ten-bar elapsed time
is 13 calendar days: **0.1478%** simple opportunity cost. Actual outcomes use actual
stock endpoints and ACT/ACT 365/366 fractions, not bars/252 or bank-discount yield.
This constant-yield proxy excludes bill mark-to-market, spreads and taxes. Equities
have different risks. Current-yield scenarios are not historical cash excess.
Source: [Treasury feed documentation](https://home.treasury.gov/treasury-daily-interest-rate-xml-feed).

## 11–12. Exit research architecture and signal-specific context

One ATR distance, full ten-bar MAE/MFE quartiles, ratio of medians and full twenty-bar
time-to +2/+5/+10% form the Exit Research Envelope. Timing denominators retain
non-hits. Current severity, identity, relative weakness, SPY regime and causal ATR
context are available for future separately registered policies, not selection now.

| Ticker | Ten-bar median MAE | Ten-bar median MFE | Median MFE / absolute median MAE |
| --- | ---: | ---: | ---: |
| C | -2.857% | +5.368% | 1.879 |
| GE | -3.923% | +4.313% | 1.100 |
| HD | -4.048% | +2.640% | 0.652 |

EXP-004's fold-varying winners are not one frozen prospective adaptive policy.
Adaptive stop/target and outcomes are **unavailable** until separately registered.
Ten-bar holding is the simple comparator; +10%/-7% is only the historical V1
control. The future portfolio contract has no allocation defaults or simulator;
capital, capacity, overlap, timing, cash and costs require advance registration.

## 13–14. Archive status and reliability

Original decisions/context/vintages/hash seals remain immutable. Today and status
are separate sidecars. Outcome updates append stock/SPY vintages and separately
versioned control/SPY/cash benchmarks. Individual returns and aggregate performance
remain sealed; maturity and operational counts may be viewed daily.

Transient acquisitions retry at most three times and retain every attempt. Invalid
OHLC fails without repair. Duplicates return original decisions without new
acquisition. Interrupted originals cannot be promoted; missing SPY, stale data and
partial coverage remain failures. Machine status retains session/start/publication,
counts, provider, configuration/code identity and expected entry opportunity.

Pointers replace atomically with bounded Windows sharing retries. A Vite watch
lock required excluding generated exports and serving their JSON directly in
development; hashes and immediate availability of new generations were checked.
Production builds remain ordinary static files.

## 15–18. Verification, Git and current failures

Final counts are in `RESEARCH_LOG.md`. Backend tests cover clocks/DST, universe,
failures, future-bar invariance, repeatability, historical cutoffs, cash, immutable
attachments, duplicates/interruptions and atomic replacement. Real-data browser
tests exercise candidates/context, sorting/filtering, sealed evidence, all existing
views and desktop/mobile behavior. Generated market files remain ignored.

Protocol commit: `4925d8b`; implementation: `5526304`; operational/export/browser
verification follows in a meaningful completion commit. All are pushed to
origin/main. Original records retain the clean implementation revision.

All 23 failures are malformed OHLC (open/close outside low/high) in returned
adjusted history: ABBV, ABT, AMT, BAC, CMCSA, DUK, GM, IBM, KO, LMT, MDT, MMM, MO,
MRK, NEE, PFE, PG, PM, T, TXN, VZ, WFC, XOM. All names remain present. No observation
or rate was fabricated. The previous 275-file output/archive inventory is unchanged;
frozen source/configuration checks also pass.

## 19–20. Daily commands and daily inspection

Use a clean revision and the Athens collection window on Today:

```powershell
.\.venv\Scripts\python.exe -W error -m scripts.run_today
.\.venv\Scripts\python.exe -W error -m scripts.update_prospective_outcomes
.\.venv\Scripts\python.exe -W error -m scripts.verify_prospective
.\.venv\Scripts\python.exe -m scripts.build_dashboard_data
```

Reload Today. Check session/freshness/failures first, then components, prior history
and exit envelope, then archive maturity/coverage. Outside-window collection is
snapshot only, never prospective backfill. `python -m scripts.run_today --offline`
verifies the retained snapshot and refreshes the export. See
[daily instructions](DAILY_RESEARCH.md) for recovery and snapshot options.

## 21–22. Evidence threshold and recommended next milestone

Reviews remain 2027-04-01 and 2027-10-01: at least 100 scheduled sessions and 80%
all-name complete timely runs. Count milestones never open an earlier review;
fewer than 100 mature events cannot support a strong conclusion. Strong descriptive
support requires positive net EV, SPY excess and median, acceptable downside,
two-calendar-quarter and majority-ticker breadth, and limited concentration. Cash
excess adds opportunity-cost context. A hold improvement also needs positive paired
EV without worse fifth-percentile return or mean loss. Dependence and uncertainty
remain; none of this proves future profitability.

Next: **data-source compatibility and daily coverage**. Diagnose retained OHLC
failures, validate adjustment arithmetic and identity, and separately register any
compatible acquisition change. Persistent failures would prevent the unchanged
coverage gate from passing. Do not drop stocks, relax validation/gates, tune V1 or
start another optimization experiment.
