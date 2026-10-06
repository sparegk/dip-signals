"""Audited raw-boundary equality adjustment; strict validation remains unchanged."""

import numpy as np
import pandas as pd
import yfinance as yf

from src.data import PROVENANCE_KEY, clean_data, normalize_ticker, _date_range

POLICY = 'raw-boundary-equality-v1'
EFFECTIVE_SESSION = '2026-10-06'


def adjust_paired(raw: pd.DataFrame, ticker: str) -> tuple[pd.DataFrame, list[dict]]:
    """Only exact raw ties may reconcile a one-step adjustment round-trip error.

    Validate source OHLC first. Keep every previously valid adjusted row bitwise
    unchanged, including close. A tie is mathematical evidence, not a tolerance
    for malformed provider prices. Every changed high/low is explicitly recorded.
    """
    clean_data(raw, ticker)  # strict unadjusted OHLC, timestamps, identity, volume
    if 'Adj Close' not in raw:
        raise ValueError('Paired adjusted close required')
    adj = raw['Adj Close'].to_numpy(dtype=float)
    if not np.isfinite(adj).all() or (adj <= 0).any():
        raise ValueError('Adjusted close must be finite and positive')
    factor = adj / raw.Close.to_numpy(dtype=float)
    if not np.isfinite(factor).all() or (factor <= 0).any():
        raise ValueError('Invalid adjustment factor')
    output = yf.utils.auto_adjust(raw.copy())
    changes = []
    for boundary, violates in [('High', output.Close > output.High),
                                ('Low', output.Close < output.Low)]:
        for i in np.flatnonzero(violates.to_numpy()):
            before, after = float(output[boundary].iloc[i]), float(output.Close.iloc[i])
            # Exactly adjacent float AND exact raw equality. Never broad epsilon.
            if (raw[boundary].iloc[i] != raw.Close.iloc[i]
                    or np.nextafter(before, after) != after):
                raise ValueError('Adjustment discrepancy lacks exact boundary evidence')
            changes.append({'session': raw.index[i].isoformat(), 'field': boundary,
                            'before': before, 'after': after, 'raw_boundary': float(raw[boundary].iloc[i]),
                            'raw_close': float(raw.Close.iloc[i]), 'factor': float(factor[i]),
                            'reason': 'exact raw boundary equality; adjacent binary64 round trip'})
            output.iloc[i, output.columns.get_loc(boundary)] = after
    output.attrs = raw.attrs.copy()
    output.attrs[PROVENANCE_KEY] = dict(raw.attrs.get(PROVENANCE_KEY, {})) | {
        'adjustment': POLICY, 'adjustment_changes': changes}
    clean_data(output, ticker)  # no relaxation at ingestion/storage boundaries
    return output, changes


def download_paired(ticker: str, *, start: str, end: str) -> pd.DataFrame:
    """Single raw/adjusted-close vintage, with actions and no automatic repair."""
    from datetime import datetime, timezone
    ticker = normalize_ticker(ticker)
    start, end = _date_range(start, end)
    try:
        raw = yf.download(ticker, start=start, end=end, interval='1d', auto_adjust=False,
            back_adjust=False, actions=True, repair=False, keepna=True, rounding=False,
            progress=False, threads=False, ignore_tz=True, multi_level_index=False, timeout=30)
    except Exception as exc:
        raise RuntimeError(f'Download failed for {ticker}: {exc}') from exc
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        raise RuntimeError(f'No paired data returned for {ticker}')
    raw.attrs[PROVENANCE_KEY] = {'schema_version': 1, 'ticker': ticker, 'provider': 'yfinance',
        'provider_version': yf.__version__, 'interval': '1d',
        'adjustment': 'auto_adjust=False; actions=True; provider-reported volume',
        'requested_start': start, 'requested_end': end,
        'retrieved_at': datetime.now(timezone.utc).isoformat()}
    return raw


def verify_adjustment(root, item: dict) -> None:
    """Replay from paired bytes; evidence and transformed bytes must both match."""
    if not item.get('paired_sha256'):
        if item.get('adjustment_policy') == POLICY:
            raise ValueError('Paired adjustment evidence missing')
        return  # legacy vintages remain strict and unchanged
    from src.data_audit import restore_raw
    from pandas.testing import assert_frame_equal
    raw = restore_raw(root, {'raw_sha256': item['paired_sha256']})
    expected, changes = adjust_paired(raw, item['ticker'])
    if item.get('adjustment_policy') != POLICY or item.get('adjustment_changes') != changes:
        raise ValueError('Adjustment evidence mismatch')
    actual = restore_raw(root, item)
    try:
        assert_frame_equal(expected, actual, check_exact=True)
        if item.get('validated_sha256'):
            from src.data import load_parquet
            validated = load_parquet(root/'objects'/item['validated_sha256'], ticker=item['ticker'])
            assert_frame_equal(clean_data(actual, item['ticker']), validated,
                               check_exact=True, check_dtype=False)
    except AssertionError as exc:
        raise ValueError('Adjustment replay mismatch') from exc
