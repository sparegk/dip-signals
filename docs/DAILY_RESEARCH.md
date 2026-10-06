# Daily quantitative research

Open the local frontend at http://127.0.0.1:5173/#today. Today is the default.
This is a saved daily research workstation, not an intraday feed or trading system.

From the repository root, with a clean committed revision:

```powershell
.\.venv\Scripts\python.exe -W error -m scripts.run_today
.\.venv\Scripts\python.exe -W error -m scripts.update_prospective_outcomes
.\.venv\Scripts\python.exe -W error -m scripts.verify_prospective
.\.venv\Scripts\python.exe -m scripts.build_dashboard_data
```

Run collection during the window shown on Today: after 00:15 New York following
the completed session, before the next regular open. Athens times are calculated
with timezone rules; normally this starts at 07:15, with US/European DST transition
weeks differing. Holidays and early closes come from the XNYS calendar. No daily
bar from an open session is treated as complete. No scheduler was installed.

Outside this window `run_today` collects a **Current Market Snapshot** in a separate
archive; it never backfills prospective evidence. `--snapshot-only` explicitly
disables enrollment; `--refresh` requests a new snapshot vintage, never replacement
of an original prospective run. `--offline` replays the retained latest snapshot
and refreshes the export without acquisition. The clock is never caller-supplied.
Offline mode can show stale data and does not enlarge prospective evidence.

Each day inspect session/freshness, publication time, 95-name coverage and failure
reasons first. Then inspect V1 events, their four components and thresholds, prior
historical references, SPY context and exit envelope. A continuing V1 condition is
not a new event. The optional monitor reports 0/4 through 4/4 without an almost-
signal threshold. Sort columns individually; no combined score or ranking exists.

## Storage and failure handling

Original enrollment remains in `data/paper_archive`. Per-run `today/` and
`collection_status/` sidecars are immutable, hashed and reproducible. Current-only
snapshots live under `data/current_market`. Its small `latest.json` pointer is
atomically replaced; retained decision bytes are never replaced. Browser exports
are compact, content-addressed generations; Python owns all calculations.

The Vite development server serves export JSON directly and excludes generated
data from its watcher, avoiding Windows manifest locks while making new generations
immediately available. Restart Vite once after updating its configuration; reload
the page after an export. Production hosting serves ordinary static exports.

Acquisition retries transient failures up to three times, preserving every attempt
under `runs/<id>/attempts/<ticker>/`. Invalid OHLC is retained as failure without
repair. Partial runs remain partial, and the daily command exits nonzero after
exporting their status. Original valid per-ticker decisions can still be retained,
but the **all-name complete-run gate** is not satisfied. An interrupted original
cannot be resumed into successful evidence. Use the documented archive recovery
and an explicit correction; corrections never replace the original holdout.

An integrity exception is a hard failure. Do not delete archives to retry. Local
hashes are not independent timestamp witnesses or tamper-proof storage. Maintain
backups. All market data, rates, archives and generated browser data remain ignored.

Verification replays original V1/context enrollment, all outcomes and benchmark
sidecars. To verify a separate snapshot:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_prospective --snapshot-root data/current_market/snapshot-YYYY-MM-DD --run-id snapshot-YYYY-MM-DD
```

## Evidence and exit information

Historical references require 20 completed same-ticker events per horizon. All
inputs and full forward windows stop before the earlier of the signal and
2026-10-05. This keeps accumulating prospective outcomes sealed. Historical V1 EV
uses the original stop/target control and registered costs on fully mature events;
the cross-sectional reference is shown separately. These are new descriptive
vintages, not replacements for EXP-001–004 and not predictions.

SPY is paired at each stock's actual entry and endpoint session. Ready non-condition
observations and all ready observations are separate historical/prospective controls.
Cross-sectional differences are descriptive, with overlap, survivor selection and
missing-input limits. The Treasury feed uses the official 13-week investment yield
(`ROUND_B1_YIELD_13WK_2`, `QUOTE_DATE` in the current XML schema), not the discount
yield. The endpoint and schema were checked before live collection; see the
[Treasury feed documentation](https://home.treasury.gov/treasury-daily-interest-rate-xml-feed).
Annual yield is converted with elapsed calendar days and 365/366 denominators.
Current-yield scenarios are separate from historical returns. Prospective cash
excess requires a decision-linked quote recorded before entry; absent quotes stay
unavailable. This is an accrual opportunity-cost approximation, not bill total return.

The exit envelope reports prior full ten-bar MAE/MFE quartiles and their median
magnitude ratio, one ATR distance and prior full twenty-bar rebound timing with
non-hits retained. No tighter/wider stop is automatically recommended. EXP-004's
fold-varying winners are not a single prospectively frozen adaptive rule. Adaptive
stop/target and outcomes remain unavailable until such a policy is registered.

Outcome attachment appends new retained stock/SPY vintages, 1/3/5/10/20-bar maturity,
the two registered exits and separately versioned benchmark outcomes for original
events and ready control observations. Missing observations remain pending. Individual
returns and aggregate performance remain sealed until the registered review; daily
counts may be viewed. `review_prospective` also seals the benchmark review at those
same gates. Portfolio allocation is only an explicit future contract, with no defaults
and no equity curve or portfolio drawdown.

## What would count as support?

The first review remains 2027-04-01, then 2027-10-01: at least 100 scheduled sessions
and 80% all-name complete timely runs. Count milestones 50/100/250/500 never open an
early review. Fewer than 100 completed events cannot support a strong conclusion.
Positive net EV, positive SPY excess and median, acceptable downside, two-quarter
breadth, majority-ticker breadth and limited concentration are needed for strong
descriptive support. A hold improvement also requires positive paired EV difference
without worse fifth-percentile return or mean loss. Cash excess adds opportunity-
cost context; it does not weaken or replace the existing criteria. Dependence and
uncertainty still prevent these categories from proving future profitability.

Next milestone: improve collection coverage and diagnose persistent provider/data
failures without changing the frozen universe, V1 or review gates. A replacement
data source needs a separately documented compatibility/identity validation.
