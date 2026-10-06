# Flexible risk management research foundation

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

4652 complete ten-bar trades; 4433 complete twenty-bar paths.


<details><summary>Winner/loss MAE and volatility-normalized distributions</summary>

Signed MAE percentiles run from more negative at p10 to less negative at p90.
Normalized MAE is a positive adverse magnitude, so its ordering reverses.

| cohort | metric | count | p10 | p25 | p50 | p75 | p90 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| control_winners | full_10bar_mae | 2432 | -0.047148067969426499 | -0.03116734167633 | -0.016789885758894799 | -0.0078456017138853005 | -0.0031292245857960001 |
| control_winners | mae_atr | 2432 | 0.121169719348845 | 0.28069520809012838 | 0.64155245403747618 | 1.0968379565823692 | 1.6801124917050647 |
| control_winners | mae_before_first_recovery_close | 2432 | -0.036704709627854402 | -0.0218170773171 | -0.0101929825939822 | -0.0040776709944333996 | -0.0015541664213082 |
| control_losses | full_10bar_mae | 2220 | -0.1297558164485787 | -0.091190392473539897 | -0.063013770290133303 | -0.040230845402590802 | -0.026124475503633199 |
| control_losses | mae_atr | 2220 | 1.0775671892731953 | 1.5857487508504255 | 2.2771051057907989 | 3.1382477208610329 | 4.2868805307393698 |
| control_losses | mae_before_first_recovery_close | 1747 | -0.078531956085278007 | -0.039842908479090798 | -0.0148094583825614 | -0.0055200850539547002 | -0.0023395972608949 |
| hold_winners | full_10bar_mae | 2542 | -0.055172109285233299 | -0.034287285510281901 | -0.0177619942905578 | -0.0081934354999904004 | -0.0032759803527524002 |
| hold_winners | mae_atr | 2542 | 0.12564705458294631 | 0.29481757795696778 | 0.66634622890159401 | 1.2101081864293981 | 1.8215560734377916 |
| hold_winners | mae_before_first_recovery_close | 2542 | -0.043724583610828399 | -0.024136920042858199 | -0.010882806132758899 | -0.0043749104403074997 | -0.0016805386512647 |
| hold_losses | full_10bar_mae | 2110 | -0.13055473350489691 | -0.0892645331005196 | -0.060256742357073602 | -0.038693520896604897 | -0.0256374085812444 |
| hold_losses | mae_atr | 2110 | 1.0556987855281077 | 1.5577714797541411 | 2.2862788671756729 | 3.1984207936223594 | 4.3479432872335044 |
| hold_losses | mae_before_first_recovery_close | 1637 | -0.063868882497994897 | -0.032707822147959503 | -0.013099898863348799 | -0.0050532398669711999 | -0.0021542241338193 |

</details>

<details><summary>Entry-time covariates: means, medians and interquartile ranges</summary>

| cohort | feature | count | mean | p25 | median | p75 |
| --- | --- | --- | --- | --- | --- | --- |
| control_winners | atr_pct_14 | 2432 | 0.029702401205494201 | 0.0205693260332197 | 0.026381697468107802 | 0.034311094459308203 |
| control_winners | drawdown_60d | 2432 | -0.13296629490327011 | -0.16969973399684771 | -0.11283661783787211 | -0.073036285875786394 |
| control_winners | price_zscore_20d | 2432 | -1.6333443386136579 | -1.9631499814217044 | -1.5489765432548082 | -1.2470031266519848 |
| control_winners | relative_return_10d | 2432 | -0.047942071026353401 | -0.067624937375804606 | -0.046453980828103002 | -0.026211082311107099 |
| control_winners | relative_volume_20d | 2432 | 1.2766375385215285 | 0.89496370927380275 | 1.1018536939191446 | 1.414478771319353 |
| control_winners | dip_component_count | 2432 | 3.2232730263157894 | 3 | 3 | 3 |
| control_winners | volatility_20d | 2432 | 0.3105267685160803 | 0.20185764845661561 | 0.2733690256066742 | 0.37625915441580637 |
| control_winners | benchmark_volatility_20d | 2432 | 0.15560853420865359 | 0.1065343928014466 | 0.13532764857384 | 0.1747031295052861 |
| control_winners | benchmark_drawdown_20d | 2432 | -0.030287152735984198 | -0.044581356981482703 | -0.017078135206282 | -0.0045654326011897997 |
| control_winners | drawdown_change_5 | 2390 | -0.035443536994138297 | -0.0527555963240312 | -0.030335793897405001 | -0.0133760263776572 |
| control_winners | bars_since_prior_dip | 2218 | 17.807484220018033 | 4 | 10 | 23.75 |
| control_losses | atr_pct_14 | 2220 | 0.0296033214743383 | 0.020868255192171101 | 0.026364073865438601 | 0.034949876807111098 |
| control_losses | drawdown_60d | 2220 | -0.1280986853785612 | -0.1658208562531551 | -0.1086519831875634 | -0.0714710899978208 |
| control_losses | price_zscore_20d | 2220 | -1.6471332222135586 | -1.985363840955348 | -1.5846562822400911 | -1.2567119226630048 |
| control_losses | relative_return_10d | 2220 | -0.050886002785884898 | -0.068795843084334493 | -0.048008366282975203 | -0.029593541939169899 |
| control_losses | relative_volume_20d | 2220 | 1.3182797824387684 | 0.89005231886870095 | 1.1051365681718006 | 1.4278079828508692 |
| control_losses | dip_component_count | 2220 | 3.2450450450450448 | 3 | 3 | 3 |
| control_losses | volatility_20d | 2220 | 0.31305732346338527 | 0.20309412296212301 | 0.27635122264312512 | 0.37289606921364171 |
| control_losses | benchmark_volatility_20d | 2220 | 0.1476631745844926 | 0.1016810956043588 | 0.13115077925146171 | 0.1731277943376324 |
| control_losses | benchmark_drawdown_20d | 2220 | -0.026527148685054899 | -0.040999273935590497 | -0.0153237374930358 | -0.0030660889376450001 |
| control_losses | drawdown_change_5 | 2170 | -0.035293187250839103 | -0.0512129985969242 | -0.029332887152600101 | -0.013158054584998099 |
| control_losses | bars_since_prior_dip | 1998 | 19.108108108108109 | 4 | 10 | 27 |

</details>

Median ATR/close is approximately 2.638% for control winners and 2.636% for
losses. Drawdown, z-score, relative weakness and volume interquartile ranges
overlap substantially; prior-dip spacing has the same ten-bar median. Separation
of **future** MAE is strong but is not an entry-time predictor. No classifier,
threshold search, multiple-testing selection or prospective conclusion follows.

### Volatility normalization

| fold | metric | count | spearman_with_atr |
| --- | --- | --- | --- |
| all | full_10bar_mae | 4652 | -0.27742775940200559 |
| all | full_10bar_mfe | 4652 | 0.36225532862645538 |
| all | mae_atr | 4652 | -0.086762359836295197 |
| all | mfe_atr | 4652 | -0.0114873999492253 |

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

Of 902 stopped trades with complete twenty-bar paths, 367 (40.69%) recover at a later close. Median recovery among hits is bar 11 from entry. Median bar-twenty gross return from the stop fill is 2.55%; median net return from original entry is -4.88%.


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

| Category | Control losses with complete 20 bars |
| --- | --- |
| deep_drawdown_with_recovery | 361 |
| delayed_recovery | 130 |
| early_recovery | 1176 |
| immediate_failure_no_recovery | 152 |
| persistent_decline | 266 |

### Gaps and market regime

143 of 952 historical stop exits (15.02%) fill at a gap-through open.


A 7% barrier cannot guarantee a 7% realized loss. Worst subsequent overnight
gap uses open/prior close, distinct from each session's low/open adverse move;
the initial entry gap is separately reported. These are overlapping measures,
not an additive decomposition of portfolio losses. Halts/liquidity and intraday
execution are not observable in daily bars. No portfolio drawdown is claimed.

| context | group | count | loss_fraction | control_ev | hold_ev | mean_loss | worst_loss | p5 | median_mae | median_mae_atr | gap_stops |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| regime | above | 3562 | 0.47866367209432897 | 0.0044954565684950003 | 0.0080461016952433993 | -0.041868950847883099 | -0.28966972278045028 | -0.071115330745786007 | -0.031876402264612802 | 1.2683590385333887 | 82 |
| regime | below | 1090 | 0.47247706422018337 | 0.0062135888140623001 | 0.0140448408981079 | -0.057375707504388397 | -0.28789848454674921 | -0.072841844578193704 | -0.045427975570196101 | 1.3550507040759681 | 61 |
| volatility_group | high | 758 | 0.48284960422163581 | 0.010089075642972199 | 0.0250798347833904 | -0.067451280681610895 | -0.28789848454674921 | -0.076676664194709102 | -0.058050160131474002 | 1.120597191035984 | 54 |
| volatility_group | low | 1006 | 0.47614314115308137 | 0.00059959299495159998 | 0.0008676377890293 | -0.031202269146193999 | -0.1087616810551173 | -0.071115330745785896 | -0.0247434362318249 | 1.4608523996785747 | 14 |
| volatility_group | middle | 2888 | 0.47610803324099721 | 0.0050328664175945002 | 0.0083399350539546998 | -0.0445832690253848 | -0.28966972278045028 | -0.071115330745786007 | -0.0353787292433249 | 1.277833242872255 | 75 |

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
