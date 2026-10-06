"""Render retained data-quality and historical loss findings into documentation."""

import json
from pathlib import Path

import pandas as pd

from src.data_audit import restore_raw
from src.preservation import digest, get_object, read_record


def table(frame: pd.DataFrame) -> str:
    columns=list(frame.columns)
    def value(x):
        if pd.isna(x): return 'unavailable'
        if isinstance(x,float): return format(x,'.17g')
        return str(x).replace('|','/')
    return '\n'.join(['| '+' | '.join(columns)+' |','| '+' | '.join(['---']*len(columns))+' |',
                      *['| '+' | '.join(value(x) for x in row)+' |' for row in frame.itertuples(index=False,name=None)]])+'\n'


def append_section(path: Path, marker: str, text: str) -> None:
    content=path.read_text(encoding='utf-8')
    start,end=f'<!-- {marker}_START -->',f'<!-- {marker}_END -->'
    section=start+'\n'+text.rstrip()+'\n'+end+'\n'
    if start in content:
        a,b=content.index(start),content.index(end)+len(end)
        content=content[:a]+section.rstrip()+content[b:]
    else:
        content=content.rstrip()+'\n\n'+section
    path.write_text(content,encoding='utf-8')


def run() -> None:
    root=Path('data/current_failure_audit')
    audit=read_record(root/'audit-paired.json')
    universe=read_record(root/'universe-validation.json')
    original=pd.DataFrame(audit['original_observations'])
    summaries=pd.DataFrame([{'Ticker':r['ticker'],'Affected candles':r['affected_rows'],
                             'Classification':r['classification'],'Max spacing units':r['max_spacing_units'],
                             'Independent price check':'unavailable (Stooq browser challenge)'}
                            for r in audit['original_failures']])
    identity=[]; inputs=[]
    sec=json.loads(get_object(root,read_record(root/'external/sec-identities.json')['raw_sha256']))
    current={r[2]:r for r in sec['data']}
    for r in audit['original_failures']:
        ticker=r['ticker']; mapping=current[ticker]
        submission=read_record(root/'external'/f'sec-submissions-{ticker}.json')
        detail=json.loads(get_object(root,submission['raw_sha256']))
        paired=read_record(root/'paired'/f'{ticker}.json')
        frame=restore_raw(root,paired)
        identity.append({'Ticker':ticker,'Current issuer':mapping[1], 'CIK':mapping[0], 'Exchange':mapping[3],
            'Share class':'Class A common' if ticker=='CMCSA' else 'common / ordinary; full share-class history unresolved',
            'SEC former names':'; '.join(x['name'] for x in detail['formerNames']) or 'none reported',
            'Dividend rows':int(frame.Dividends.ne(0).sum()), 'Split rows':int(frame['Stock Splits'].ne(0).sum())})
        inputs.append({'Ticker':ticker,'Collected UTC':r['input']['provenance']['retrieved_at'],
                       'Original raw SHA256':r['input']['raw_sha256'], 'New paired SHA256':paired['raw_sha256']})
    exact=[]; paired_rows=[]
    for row in original.to_dict('records'):
        ticker=row['ticker']; raw=restore_raw(root,read_record(root/'paired'/f'{ticker}.json'))
        source=raw.loc[pd.Timestamp(row['session'])]
        boundary='High' if row['rule']=='close_gt_high' else 'Low'
        exact.append({'Ticker':ticker,'Session':row['session'][:10],
                      **{x:row[x] for x in ['open','high','low','close','rule','absolute_gap']},
                      'new raw boundary=close':bool(source[boundary]==source.Close)})
        paired_rows.append({'Ticker':ticker,'Session':row['session'][:10],
                            **{key:source[key] for key in ['Open','High','Low','Close','Adj Close','Dividends','Stock Splits']},
                            'factor':source['Adj Close']/source.Close,
                            'round_trip_close':source.Close*(source['Adj Close']/source.Close)})
    text='''## 2026-10-06 retained EXP-005 failure investigation

Confirmed: **23 failed names, 41 exact offending candles**, all close-boundary
violations of one binary64 spacing unit. No observed open-boundary, inverted range,
missing, stale, duplicate or session defect explains these 23 original rejections.
Original run `exp005-2026-10-05` remains **72/95, partial**, not repaired.
All original failure inputs, attempts, code identity and configuration hashes remain
immutable. This report supplements, and does not replace, EXP-003 findings above.

Each name was measured independently:

'''+table(summaries)+'''
<details><summary>Every original malformed candle (17 significant digits)</summary>

These are the original adjusted returned prices. The raw tie confirmation is from
a **new** paired vintage, not a reconstruction of absent original unadjusted prices.

'''+table(pd.DataFrame(exact))+'''

Paired raw/adjusted-close operands at each original offending date (new vintage):

'''+table(pd.DataFrame(paired_rows))+'''

Every reproduced new-vintage failure and its adjustment arithmetic:

'''+table(pd.DataFrame(audit['paired_observations'])[[
    'ticker','session','raw_open','raw_high','raw_low','raw_close','adjusted_close','factor',
    'round_trip_close','rule','absolute_gap','spacing_units']])+'''
</details>

The original configuration hash is `933568a3bc8881bd30c16cce3efa80bfacc68f0094cba21becd280b353a81312`;
code revision `5526304dae77771e708340899fe50feac9816fdc`. The immutable audit envelope
also retains every original source hash, provider, collection timestamp, error and
session. Original raw objects live under `data/paper_archive/objects/`; new paired,
SEC and independent-request responses under `data/current_failure_audit/objects/`.

<details><summary>Per-ticker retained references and identity/action checks</summary>

'''+table(pd.DataFrame(inputs))+'\n'+table(pd.DataFrame(identity))+'''
</details>

### Arithmetic evidence and narrowly scoped change

Installed yfinance computes `f = Adj Close / Close`, scales Open/High/Low by f,
and copies Adj Close to Close. For exact raw close/high or close/low ties,
division followed by multiplication can produce a neighboring float instead of
Adj Close. New paired responses reproduce **30 such violations** for the 23 names;
every reproduced violation has exact raw boundary equality and one-step error.
All **41 original affected dates** also have the corresponding raw equality in
the new vintage. Changed adjustment factors/vintages alter which dates fail;
the original factor cannot be conclusively reconstructed without original pairs.

The new data-only policy `raw-boundary-equality-v1` validates unadjusted OHLC
strictly first, preserves the same installed adjustment calculation, and only
when an adjusted close-boundary violation has BOTH exact raw equality and exactly
one adjacent float, assigns that boundary the identical adjusted-close value.
Every field, before/after value, raw operands, factor and reason is retained.
Close is unchanged. All previously valid adjusted rows remain bitwise unchanged.
Strict `clean_data`, Parquet validation and old cache behavior are unchanged.
No generic epsilon, clipping of malformed raw prices, filling, row deletion or
strategy threshold change is allowed. Legacy adjusted responses without paired
evidence remain rejected, including all original failures.

Applied to all new diagnostic vintages: **95/95 stocks plus SPY pass**.
Of 96 responses, 77 already passed strict adjustment; 19 required 37 recorded
boundary transformations. These are new diagnostic bytes, **not** an improvement
of the original prospective coverage record. First effective prospective signal
session is **2026-10-06**, collected October 7 in the unchanged registered window.
Future availability, freshness and timely all-name completion are still required.
The 100-session / 80%-complete gate is not passed by this engineering check.

### Identity findings and remaining uncertainty

The retained [official SEC ticker/exchange mapping](https://www.sec.gov/files/company_tickers_exchange.json)
and all 23 issuer submission responses confirm current symbol/name/exchange
associations, not complete historical share-class continuity. CMCSA is listed Class A,
with unlisted Class B separately documented in its [issuer FAQ](https://cmcsa.gcs-web.com/shareholder-services/faqs).
Former-name arrays are issuer histories, not a permanent security-level ticker ledger;
absence of a former name is not proof of no ticker reuse. No symbol is substituted.

Important action/history boundaries: [IBM/Kyndryl, November 2021](https://www.ibm.com/investor/news/ibm-completes-separation-of-kyndryl),
[3M/Solventum, April 2024](https://news.3m.com/2024-03-08-3M-Board-of-Directors-Approves-Spin-off-of-Solventum),
[Merck/Organon, June 2021](https://www.merck.com/news/merck-announces-completion-of-organon-co-spinoff/),
and [AT&T/WarnerMedia, April 2022](https://investors.att.com/stock-information/historical-stock-information/warnermedia-transaction/warnermedia-transaction).
XOM now maps to ExxonMobil Holdings (CIK 2115436), rather than former CIK 34088;
the [issuer filing](https://www.sec.gov/Archives/edgar/data/34088/000003408826000093/xom-20260630.htm)
documents a July 1, 2026 redomiciliation merger. This is an actual identity warning,
distinct from the 2018 boundary error. Medtronic's holding-company history and
General Motors' predecessor identity also require security-master care. These
facts do not establish corporate actions caused the numerical failures.
Provider unadjusted OHLC may itself already incorporate splits; it is not an
unrevised exchange tape. Dividend/split rows above are provider-reported counts,
not independent action-factor validation. Full corporate-action and historical
security continuity remain unresolved; no PIT claim is made.

### Independent market-price comparison

All 23 Stooq requests returned retained HTML browser-verification responses,
not CSV bars. No prices were parsed from them and no challenge was bypassed.
The first Nasdaq historical request returned a retained application-level
date-range error; a corrected multi-day request returned zero records. Both
responses remain retained. Neither provides an independent price comparison.
Thus **primary value vs independent value agreement is unverified for all 41
candles**. Different vendors' adjustment conventions also require reconciliation
before comparison. Independent raw-price verification remains an explicit next
milestone; the transformation fix is supported by exact paired arithmetic, not
by a claimed independent price match or strategy profitability.

Reproduce offline:

```powershell
.\\.venv\\Scripts\\python.exe -W error -m scripts.audit_current_failures --universe
.\\.venv\\Scripts\\python.exe -m scripts.report_loss_foundation
```

Use `--download --external` for a new root only when a disclosed new vintage is
needed. Existing records are idempotent; conflicts fail, and failures stay retained.
'''
    append_section(Path('docs/DATA_QUALITY_AUDIT.md'),'CURRENT_FAILURE_AUDIT',text)
    loss=Path('data/loss_diagnostics_v2')
    summary=read_record(loss/'summary.json')
    tables={name:pd.read_csv(loss/f'{name}.csv') for name,h in summary['artifacts'].items()
            if digest((loss/f'{name}.csv').read_bytes())==h}
    if len(tables)!=len(summary['artifacts']): raise ValueError('Diagnostic artifact changed')
    q=tables['quantiles'];c=tables['covariates'];r=tables['regimes'];e=tables['events']
    stopped=e.loc[e.observed_bars.eq(20)&e.stop_out]
    text='''# Flexible risk management research foundation

**Entry-time winners and losers substantially overlap.** These consumed historical
diagnostics justify investigating conditional risk distributions, but do not
establish a stable entry predictor or an improved exit. No new rule is deployed.
Prospective outcomes are untouched and sealed under EXP-005.

## Definitions recorded for diagnosis

Source: hash-verified frozen EXP-002 observations and independent completed V1
control trades, 2021-2026 folds, all 74 usable original names. Exclude any row
on/after 2026-10-05 before calculation. Require full ten-bar paths within the
original fold; twenty-bar categories additionally require full twenty bars.
Historical adjusted prices, universe survivorship and dependent overlapping events
remain limitations. We do not replace the original experiment results.

Control winners have positive net return; losses include zero/nonpositive net.
The no-barrier ten-bar hold is separately labeled using the original 1 bp commission
plus 5 bp slippage per side. All path extrema are outcomes, never covariates.
Full-path MAE/MFE differs from the frozen control's excursion through its exit.
ATR-normalized adverse magnitude is `abs(full MAE) / signal-day (ATR14/close)`;
the denominator is frozen at the signal, never recomputed from future volatility.
Volume, relative weakness, drawdown, components and SPY state are signal-time
measurements. Entry gaps are subsequent information and excluded from covariates.
Prior-dip spacing uses only prior same-ticker events visible in the original fold;
first visits are unknown rather than assumed to have no earlier history.

## Measured historical results

'''+f"{summary['events']} complete ten-bar trades; {summary['complete_20bar_paths']} complete twenty-bar paths.\n\n"+'''
<details><summary>Winner/loss MAE and volatility-normalized distributions</summary>

Signed MAE percentiles run from more negative at p10 to less negative at p90.
Normalized MAE is a positive adverse magnitude, so its ordering reverses.

'''+table(q.loc[q.metric.isin(['full_10bar_mae','mae_atr','mae_before_first_recovery_close'])])+'''
</details>

<details><summary>Entry-time covariates: means, medians and interquartile ranges</summary>

'''+table(c.loc[c.cohort.str.startswith('control')])+'''
</details>

Median ATR/close is approximately 2.638% for control winners and 2.636% for
losses. Drawdown, z-score, relative weakness and volume interquartile ranges
overlap substantially; prior-dip spacing has the same ten-bar median. Separation
of **future** MAE is strong but is not an entry-time predictor. No classifier,
threshold search, multiple-testing selection or prospective conclusion follows.

### Volatility normalization

'''+table(tables['correlations'].loc[tables['correlations'].fold.eq('all')])+'''
ATR has descriptive Spearman correlations -0.277 with signed MAE and +0.362
with MFE. Normalization reduces the corresponding associations to approximately
-0.087 and -0.011. This supports studying risk in volatility units, but low/middle/
high ATR groups still have different normalized adverse distributions. Normalization
does not remove stock/regime dependence or establish an acceptable loss budget.

### Stopped, then recovered

Only the **already frozen 7% historical control** is inspected. No hypothetical
stop grid is searched. Recovery means a later close above original entry after
the frozen round-trip costs, strictly after the exit session; same-day intraday
sequence is unknown and excluded. The window ends at bar twenty, not infinity.

'''+f"Of {summary['stops_with_20bar_path']} stopped trades with complete twenty-bar paths, "\
       f"{summary['recover_after_stop']} ({summary['recover_after_stop']/summary['stops_with_20bar_path']:.2%}) recover at a later close. "\
       f"Median recovery among hits is bar {summary['median_recovery_bar_after_stop']:.0f} from entry. "\
       f"Median bar-twenty gross return from the stop fill is {stopped.stop_price_to_20bar_return.median():.2%}; "\
       f"median net return from original entry is {stopped.net_return_at_20bar.median():.2%}.\n\n"+'''
Recovery fractions include all stopped complete paths, including non-recoveries.
Fifty stopped paths lack twenty-bar maturity and are excluded from this comparison,
not discarded from the ten-bar/control sample. Rebound opportunities after a stop
do not prove that remaining exposed would improve risk-adjusted expectancy.

### Loss path categories

Mutually exclusive descriptive hierarchy: incomplete twenty bars = censored;
deep ten-bar adverse movement at least the old control distance followed by a
positive-net close from the ten-bar trough onward; otherwise first positive-net
close after bar ten = delayed recovery; otherwise any early recovery; otherwise
negative bar-twenty return no better than bar ten = persistent decline; otherwise
negative first/ten-bar closes = immediate failure without observed recovery;
otherwise sideways/no-rebound. Labels are post-outcome, not signal filters.
An early positive close can still lead to a losing control trade. Daily low-to-close
recovery is known, but intraday order relative to highs is not. 'No recovery' means
none observed within twenty bars, never 'will never recover'.

'''+table(pd.DataFrame([{'Category':k,'Control losses with complete 20 bars':v}
                       for k,v in summary['loss_categories'].items()]))+'''
### Gaps and market regime

'''+f"{summary['gap_stops']} of {summary['all_stops']} historical stop exits "\
      f"({summary['gap_stops']/summary['all_stops']:.2%}) fill at a gap-through open.\n\n"+'''
A 7% barrier cannot guarantee a 7% realized loss. Worst subsequent overnight
gap uses open/prior close, distinct from each session's low/open adverse move;
the initial entry gap is separately reported. These are overlapping measures,
not an additive decomposition of portfolio losses. Halts/liquidity and intraday
execution are not observable in daily bars. No portfolio drawdown is claimed.

'''+table(r.loc[r.context.isin(['regime','volatility_group'])])+'''
Above/below causal SPY SMA200 loss frequencies are similar (47.9%/47.2%), but
average losses are approximately -4.19%/-5.74%. Market stress affects severity
without providing a demonstrated entry filter. Group boundaries for stock ATR
are the existing descriptive 2%/4% bands, not optimized stops or prospective
EXP-005 tertile boundaries. All annual-fold and component-combination tables
are retained under the ignored diagnostic root, including unfavorable groups.

## Signal quality versus risk management

- Case A (entry-quality predictor): not established. Covariate overlap is large;
  descriptive fold comparisons cannot demonstrate stable classification.
- Case B (exit/path problem): plausible; strong future-path differences and
  stopped-then-recovered events justify studying rebound duration and risk envelopes.
- Case C (market/portfolio shocks): contributes to severity; gaps and below-SMA
  losses need explicit stress/capacity/correlation treatment. No allocated evidence yet.
- Case D (no stable predictor): remains possible. Avoid over-engineering a stop.

The cause is mixed and unvalidated. Historical patterns alone are insufficient
to authorize a deployed flexible model. There is enough rationale for a separately
registered training-only research design once collection reliability is established.

## Future risk-envelope architecture (design only)

Input contract: immutable entry-time data vintage, causal ATR and regime, original
components/severity, volume and strictly mature prior-event context. Estimate joint
conditional adverse/favorable excursion and recovery-time distributions with sample
counts, uncertainty and an explicit unavailable state. Output adverse/favorable
quantiles, rebound duration and gap stress envelope; do not collapse into a magic
stop or a buy/sell/risk score. Current Today details already expose ATR, prior
MAE/MFE, event count, volatility context and SPY state as historical references.

Calibration must use training data only. Freeze features, grouping/estimation,
costs, gap assumptions, sample floors, acceptance criteria and code before multiple
chronological OOS folds and cross-sectional tests. Compare with frozen V1 and
no-stop ten-bar holding on identical entries. Do not choose the highest historical
return configuration. Preserve losing stocks and test concentration/stability.
Register portfolio allocation/capacity separately before equity curves/drawdown.
The existing consumed folds cannot become fresh OOS after this diagnosis.

Objectives: net EV, paired SPY/cash excess, average/worst loss, downside percentiles,
profit factor, drawdown under a registered portfolio, win rate and MFE capture.
Reducing losses while destroying rebounds is not success. A slightly lower win
rate may be acceptable with better net expectancy/downside under predeclared criteria.

Ranked future hypotheses: (1) ATR-conditioned excursion envelopes, (2) recovery-
duration/censoring model, (3) gap/regime stress and portfolio exposure, (4) entry-
quality covariates only if stable training evidence emerges. None changes V1 or
EXP-005. Do not optimize a stop/target, component filter, stock list, ranking,
entry delay or risk sizing now; do not peek at accumulating prospective performance.

Reproduce: `python -W error -m scripts.diagnose_losses`, then
`python -m scripts.report_loss_foundation`. All generated artifacts remain ignored.
The preliminary v1 diagnostic artifacts remain retained; v2 makes explicit that
deep drawdown recovery must occur from the trough onward. No experiment output
or prospective record was overwritten by this clarification.
'''
    Path('docs/RISK_MANAGEMENT_RESEARCH.md').write_text(text,encoding='utf-8')


if __name__=='__main__':
    run()
