"""Consumed-history loss diagnosis, never entry selection or exit optimization."""

import numpy as np
import pandas as pd

from src.backtest import apply_costs

QUANTILES = (.10, .25, .50, .75, .90)
COVARIATES = ('atr_pct_14', 'drawdown_60d', 'price_zscore_20d', 'relative_return_10d',
              'relative_volume_20d', 'dip_component_count', 'volatility_20d',
              'benchmark_volatility_20d', 'benchmark_drawdown_20d', 'drawdown_change_5',
              'bars_since_prior_dip')


def path_metrics(signal: pd.Series, path: pd.DataFrame, trade: pd.Series) -> dict:
    """Entry ATR normalization; full paths and through-exit excursions stay separate."""
    entry = float(path.iloc[0].open)
    ten = path.iloc[:10]
    atr = float(signal.atr_pct_14)
    adverse = max(0., 1-float(ten.low.min())/entry)
    favorable = max(0., float(ten.high.max())/entry-1)
    net = np.array([apply_costs(entry, float(c), commission_rate=.0001, slippage_rate=.0005)['net_return']
                    for c in path.close])
    recovery = np.flatnonzero(net > 0)
    first = int(recovery[0])+1 if len(recovery) else None
    trough = int(np.argmin(ten.low.to_numpy(float)))
    after_trough = np.flatnonzero(net[trough:] > 0)
    trough_recovery = trough+int(after_trough[0])+1 if len(after_trough) else None
    previous = np.r_[float(signal.close), path.close.to_numpy(float)[:-1]]
    gaps = path.open.to_numpy(float)/previous-1
    intraday = path.low.to_numpy(float)/path.open.to_numpy(float)-1
    stopped = trade.exit_reason == 'stop_loss'
    exit_bar = int(trade.holding_bars)
    later_hits = np.flatnonzero(net[exit_bar:] > 0) if stopped else np.array([], dtype=int)
    later_recovery = exit_bar + int(later_hits[0])+1 if len(later_hits) else None
    # Entire 20-bar window is required to distinguish late recovery from censoring.
    if len(path) < 20:
        category = 'censored_20bar'
    elif trough_recovery and adverse >= .07:
        category = 'deep_drawdown_with_recovery'
    elif first and first > 10:
        category = 'delayed_recovery'
    elif first:
        category = 'early_recovery'
    elif net[-1] <= net[9] and net[-1] < 0:
        category = 'persistent_decline'
    elif net[0] < 0 and net[9] < 0:
        category = 'immediate_failure_no_recovery'
    else:
        category = 'sideways_no_rebound'
    return {'full_10bar_mae': -adverse, 'full_10bar_mfe': favorable,
            'mae_atr': adverse/atr if np.isfinite(atr) and atr > 0 else np.nan,
            'mfe_atr': favorable/atr if np.isfinite(atr) and atr > 0 else np.nan,
            'hold_net_return': net[9], 'control_net_return': float(trade.net_return),
            'control_mae': float(trade.mae), 'control_mfe': float(trade.mfe),
            'recovery_bar': first,
            'recovery_after_10bar_trough': trough_recovery,
            'mae_before_first_recovery_close': min(0., float(path.iloc[:first].low.min())/entry-1) if first else np.nan,
            'observed_bars': len(path), 'recovery_category': category,
            'entry_gap': gaps[0], 'worst_overnight_gap': min(0., float(gaps[1:].min())) if len(gaps)>1 else np.nan,
            'worst_intraday_adverse': min(0., float(intraday.min())),
            'stop_out': stopped, 'gap_stop': bool(stopped and trade.fill_type == 'open'),
            'recovered_after_stop_bar': later_recovery,
            'net_return_at_20bar': net[-1] if len(path)==20 else np.nan,
            'stop_price_to_20bar_return': float(path.iloc[-1].close)/float(trade.exit_price)-1 if stopped and len(path)==20 else np.nan}


def diagnose_losses(observations: pd.DataFrame, trades: pd.DataFrame, *, cutoff: str) -> dict[str, pd.DataFrame]:
    """Reject post-EXP005 cutoffs; future rows are removed BEFORE any calculation."""
    if pd.Timestamp(cutoff) > pd.Timestamp('2026-10-05'):
        raise ValueError('Historical diagnosis cannot consume prospective sessions')
    obs = observations.loc[observations.timestamp.lt(pd.Timestamp(cutoff))].copy()
    trades = trades.loc[trades.timestamp.lt(pd.Timestamp(cutoff)) & trades['mode'].eq('independent')
                        & trades.status.eq('completed')].copy()
    rows = []
    for (ticker, fold), group in obs.groupby(['ticker', 'fold'], sort=True):
        group = group.sort_values('timestamp').reset_index(drop=True)
        group['drawdown_change_5'] = group.drawdown_60d.diff(5)
        previous_event = None
        lookup = trades.loc[trades.ticker.eq(ticker) & trades.fold.eq(fold)].set_index('timestamp')
        for i in np.flatnonzero(group.dip_event_v1.to_numpy(bool)):
            signal = group.iloc[i].copy()
            signal['bars_since_prior_dip'] = i-previous_event if previous_event is not None else np.nan
            previous_event = i
            if signal.timestamp not in lookup.index or i+10 >= len(group):
                continue
            trade = lookup.loc[signal.timestamp]
            path = group.iloc[i+1:i+21]
            row = {'ticker': ticker, 'fold': str(fold), 'timestamp': signal.timestamp,
                   'maturity': path.iloc[-1].timestamp, 'regime': signal.regime,
                   'component_combination': ''.join(c for c,k in zip('ABCD', (
                       'dip_drawdown_component','dip_price_zscore_component',
                       'dip_low_proximity_component','dip_relative_weakness_component')) if signal[k]),
                   **{key: signal[key] for key in COVARIATES}, **path_metrics(signal, path, trade)}
            row['volatility_group'] = 'low' if signal.atr_pct_14 <= .02 else 'middle' if signal.atr_pct_14 <= .04 else 'high'
            rows.append(row)
    events = pd.DataFrame(rows)
    quantiles, covariates, regimes, consistency = [], [], [], []
    for label, cohort in [('control_winners', events.loc[events.control_net_return.gt(0)]),
                          ('control_losses', events.loc[events.control_net_return.le(0)]),
                          ('hold_winners', events.loc[events.hold_net_return.gt(0)]),
                          ('hold_losses', events.loc[events.hold_net_return.le(0)])]:
        for metric in ('full_10bar_mae','full_10bar_mfe','mae_atr','mfe_atr','control_mae',
                       'mae_before_first_recovery_close','worst_overnight_gap','worst_intraday_adverse'):
            values = cohort[metric].dropna()
            quantiles.append({'cohort': label, 'metric': metric, 'count': len(values),
                              **{f'p{int(q*100)}': values.quantile(q) for q in QUANTILES}})
        for feature in COVARIATES:
            values = cohort[feature].dropna()
            covariates.append({'cohort': label, 'feature': feature, 'count': len(values),
                               'mean': values.mean(), 'p25': values.quantile(.25),
                               'median': values.median(), 'p75': values.quantile(.75)})
    for fold, g in events.groupby('fold', sort=True):
        winners, losers = g.loc[g.control_net_return.gt(0)], g.loc[g.control_net_return.le(0)]
        for key in COVARIATES:
            consistency.append({'fold': fold, 'feature': key, 'winners': len(winners), 'losers': len(losers),
                                'loser_minus_winner_median': losers[key].median()-winners[key].median()})
    for key in ('regime','fold','volatility_group','component_combination'):
        for value, g in events.groupby(key, dropna=False, sort=True):
            loss = g.control_net_return.le(0)
            regimes.append({'context': key, 'group': str(value), 'count': len(g), 'loss_fraction': loss.mean(),
                            'control_ev': g.control_net_return.mean(), 'hold_ev': g.hold_net_return.mean(),
                            'mean_loss': g.loc[loss,'control_net_return'].mean(),
                            'worst_loss': g.control_net_return.min(), 'p5': g.control_net_return.quantile(.05),
                            'median_mae': g.full_10bar_mae.median(), 'median_mae_atr': g.mae_atr.median(),
                            'gap_stops': int(g.gap_stop.sum())})
    correlations = []
    for group, g in [('all',events), *list(events.groupby('fold', sort=True))]:
        for metric in ('full_10bar_mae','full_10bar_mfe','mae_atr','mfe_atr'):
            pair = g[['atr_pct_14',metric]].dropna()
            correlations.append({'fold': group, 'metric': metric, 'count': len(pair),
                                 'spearman_with_atr': pair.atr_pct_14.corr(pair[metric],method='spearman')})
    return {'events': events, 'quantiles': pd.DataFrame(quantiles), 'covariates': pd.DataFrame(covariates),
            'regimes': pd.DataFrame(regimes), 'fold_consistency': pd.DataFrame(consistency),
            'correlations': pd.DataFrame(correlations)}
