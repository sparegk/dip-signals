# Hypothesis registry

EXP-005 registers the simplest next test: historical V1 exits versus ten-bar
holding, with causal volatility context as a descriptive subgroup. H4 and H7
motivate these questions; neither becomes a new signal rule. All rankings below
remain hypothesis priorities. Future evidence is pending, not validated.

No hypothesis is a validated improvement. Machine-readable definitions, risks and
proposed tests live in `config/hypotheses.json`; the frontend reads that file.

Rank favors a plausible mechanism, evidence already collected, simple causal
inputs, potential to generalize, low flexibility and feasible prospective collection.
Ranks are research priorities, not estimated probabilities or a strategy score.

| Rank | ID | Direction | Main constraint |
| --- | --- | --- | --- |
| 1 | H4 | Volatility-conditioned quality | Larger rebounds also carry larger losses |
| 2 | H7 | Rebound duration | Validate existing ten-bar hold before adaptive timing |
| 3 | H10 | Relative-to-SPY severity | Absolute profit is not stock-specific edge |
| 4 | H2 | Falling-knife avoidance | Severe weakness can also precede stronger rebounds |
| 5 | H6 | Component quality | Correlation and small subgroups |
| 6 | H5 | Market regimes | Few independent regimes; raw and excess disagree |
| 7 | H3 | Confirmation entry | Later entry may miss rebound; execution must be causal |
| 8 | H8 | Rebound-path exit | Flexible rules invite search; daily order ambiguity |
| 9 | H9 | Stock characteristics | No winning-stock whitelist |
| 10 | H1 | Repeated support | Current recorded definition has unfavorable evidence |

Historical data is for hypothesis generation. A future candidate needs a separate
registration and frozen code/configuration before its first eligible signal. A
prospective archive written from historical replay remains retrospective.

See the registered [EXP-005 protocol](EXP005_PROTOCOL.md); the earlier proposal is
retained as superseded history.

## Post-EXP-005 Edge Development

These are future research priorities, not implemented improvements. Prospective
results must be reviewed at the existing gates before a new candidate is frozen.

1. Volatility-conditioned signal quality: causal ATR context already exists;
   higher historical returns also carry larger adverse movement.
2. Rebound-duration conditioning: confirm the simple ten-bar hold before adding
   flexible timing. Historical time-only EV exceeded adaptive exits.
3. Relative-strength context: SPY excess and failed breadth make incremental
   performance a central question, rather than absolute return alone.
4. Falling-knife detection: investigate downside mechanisms without using current
   winners or losses to tune a filter.
5. Data-driven dynamic exits: MAE/MFE, duration, severity and regime can form a
   future policy interface, but historical adaptive downside is unfavorable evidence.
6. Confirmation entry: register causal execution and assess missed rebounds/costs.
7. Signal-specific risk sizing and portfolio-level selection: require a capital
   protocol, capacity/overlap assumptions and an independent validation plan.
8. Repeated-dip/support memory: lower priority because the recorded repeated-zone
   definition underperformed the no-known-zone group on historical SPY excess.

No combined ranking, new exit, sizing rule or optimization is introduced here.

## Flexible loss-control hypotheses after the data-quality audit

See [risk research foundation](RISK_MANAGEMENT_RESEARCH.md). Priority reflects
historical rationale only: (1) conditional ATR-scaled MAE/MFE distributions,
(2) recovery duration with explicit censoring, (3) gap/regime portfolio stress,
(4) entry quality only if stable training-only separation emerges. Winners and
losers currently overlap substantially at entry; future MAE differences are not
predictors. Do not infer an optimal stop from excursion percentiles or select a
filter on the consumed loss sample. Freeze any future model before genuine OOS
and leave EXP-005 unchanged. Reliable all-name collection comes first.
