"""Retained-failure audit; optional new paired vintages, never archive repair."""

import argparse
from datetime import datetime, timezone
import inspect
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf

from src.data import PROVENANCE_KEY
from src.data_audit import audit_ohlc, preserve_raw, restore_raw
from src.preservation import canonical_json, digest, put_object, read_record, write_record


def arithmetic(raw: pd.DataFrame) -> pd.DataFrame:
    """Reproduce installed auto-adjust, retaining all inputs and exact equalities."""
    factor = raw['Adj Close'] / raw.Close
    adjusted = yf.utils.auto_adjust(raw.copy())
    _, violations = audit_ohlc(adjusted, 'DIAGNOSTIC', vintage='new_diagnostic')
    rows = []
    for v in violations.to_dict('records'):
        i = v['row_position']
        source = raw.iloc[i]
        boundary = 'High' if v['rule'] == 'close_gt_high' else 'Low'
        eligible = v['rule'] in {'close_gt_high', 'close_lt_low'}
        rows.append(v | {'raw_open': source.Open, 'raw_high': source.High,
                        'raw_low': source.Low, 'raw_close': source.Close,
                        'adjusted_close': source['Adj Close'], 'factor': factor.iloc[i],
                        'raw_boundary_equals_close': bool(eligible and source[boundary] == source.Close),
                        'round_trip_close': source.Close * factor.iloc[i],
                        'dividend': source.get('Dividends', None),
                        'split': source.get('Stock Splits', None)})
    return pd.DataFrame(rows)


def audit(archive: Path, run_id: str, output: Path, *, download: bool = False) -> dict:
    """Every original failure stays linked to its actual retained vintage."""
    intent = read_record(archive / 'runs' / run_id / 'intent.json')
    result = read_record(archive / 'runs' / run_id / 'result.json')
    summaries, violations, paired = [], [], []
    output.mkdir(parents=True, exist_ok=True)
    for ticker in intent['universe']:
        original = result['inputs'][ticker]
        if original['status'] == 'available':
            continue
        summary = {'ticker': ticker, 'signal_session': intent['session'],
                   'configuration_hash': intent['config_sha256'], 'code_hash': intent['code'],
                   'input': original}
        if original.get('raw_sha256'):
            s, v = audit_ohlc(restore_raw(archive, original), ticker, vintage='original_rejected')
            summary.update(s)
            summary['classification'] = ('one_spacing_adjusted_close_boundary' if len(v) and
                v.rule.isin(['close_lt_low', 'close_gt_high']).all() and v.spacing_units.eq(1).all()
                else 'other_validation_failure')
            violations.extend(v.to_dict('records'))
        else:
            summary['classification'] = 'acquisition_failure_no_response'
        summaries.append(summary)
        target = output / 'paired' / f'{ticker}.json'
        if download and not target.exists():
            started = datetime.now(timezone.utc).isoformat()
            try:
                raw = yf.download(ticker, start='2016-09-29', end='2026-10-06', interval='1d',
                    auto_adjust=False, back_adjust=False, actions=True, repair=False, keepna=True,
                    rounding=False, progress=False, threads=False, ignore_tz=True,
                    multi_level_index=False, timeout=30)
                if raw.empty:
                    raise ValueError('Empty paired response')
                raw.attrs[PROVENANCE_KEY] = {'ticker': ticker, 'provider': 'yfinance',
                    'provider_version': yf.__version__, 'adjustment': 'auto_adjust=False; actions=True',
                    'retrieved_at': datetime.now(timezone.utc).isoformat()}
                payload = {'status': 'retained', **preserve_raw(output, raw)}
            except Exception as exc:
                payload = {'status': 'unavailable', 'error': f'{type(exc).__name__}: {exc}'}
            write_record(target, payload | {'started_at': started, 'ticker': ticker})
        if target.exists():
            payload = read_record(target)
            if payload['status'] == 'retained':
                measured = arithmetic(restore_raw(output, payload))
                measured['ticker'] = ticker
                paired.extend(measured.to_dict('records'))
        print(f'{ticker}: {summary["classification"]}', flush=True)
    findings = {'run_id': run_id, 'original_failures': summaries,
                'original_observations': violations, 'paired_observations': paired,
                'auto_adjust_source_hash': digest(inspect.getsource(yf.utils.auto_adjust).encode()),
                'limitations': ['Paired data is a new vintage, not original unadjusted evidence',
                                'No data repair, tolerance or prospective reclassification']}
    # New audit is immutable; acquisition is resumable, final report sealed once ready.
    write_record(output / ('audit-paired.json' if paired else 'audit-original.json'), findings)
    return findings


def retain_url(output: Path, name: str, url: str) -> dict:
    """One disclosed external request; failures and exact bytes are retained."""
    path = output / 'external' / f'{name}.json'
    if path.exists():
        return read_record(path)
    try:
        request = Request(url, headers={'User-Agent': 'DipSignalResearch/1.0 public data audit'})
        with urlopen(request, timeout=30) as response:
            content = response.read()
        item = {'status': 'retained', 'raw_sha256': put_object(output, content),
                'bytes': len(content)}
    except Exception as exc:
        item = {'status': 'unavailable', 'error': f'{type(exc).__name__}: {exc}'}
    item.update(url=url, retrieved_at=datetime.now(timezone.utc).isoformat())
    write_record(path, item)
    return item


def validate_universe(output: Path, *, download: bool) -> dict:
    """New diagnostic vintages only; never enroll or replace a prospective run."""
    from src.adjustment import adjust_paired, download_paired
    from src.data import clean_data
    from src.paper_archive import load_protocol
    records = []
    config = load_protocol()
    for ticker in [*config['universe'], config['benchmark']]:
        target = output/'paired'/f'{ticker}.json'
        if download and not target.exists():
            try:
                raw = download_paired(ticker, start=config['history_start'], end='2026-10-06')
                item = {'status':'retained', **preserve_raw(output, raw), 'ticker':ticker}
            except Exception as exc:
                item = {'status':'unavailable', 'ticker':ticker, 'error':f'{type(exc).__name__}: {exc}'}
            write_record(target, item)
        record = {'ticker':ticker, 'status':'unavailable'}
        if target.exists():
            item = read_record(target)
            record['input'] = item
            if item['status']=='retained':
                try:
                    raw = restore_raw(output,item)
                    adjusted = yf.utils.auto_adjust(raw.copy())
                    try:
                        clean_data(adjusted,ticker)
                        record['strict_original_pass']=True
                    except ValueError:
                        record['strict_original_pass']=False
                    result, changes = adjust_paired(raw,ticker)
                    values = ['Open','High','Low','Close','Volume']
                    valid = ((adjusted.Close<=adjusted.High)&(adjusted.Close>=adjusted.Low)
                             &(adjusted.Open<=adjusted.High)&(adjusted.Open>=adjusted.Low))
                    if not result.loc[valid,values].equals(adjusted.loc[valid,values]):
                        raise ValueError('Previously valid values changed')
                    record.update(status='available', changes=changes,
                                  transformed=preserve_raw(output,result), previously_valid_unchanged=True)
                except (ValueError,TypeError) as exc:
                    record['error']=str(exc)
        records.append(record)
        print(f'Ingestion {ticker}: {record["status"]}',flush=True)
    report = {'kind':'new_diagnostic_vintage_not_prospective', 'requested':len(config['universe']),
              'successful':sum(r['status']=='available' for r in records if r['ticker']!=config['benchmark']),
              'records':records}
    write_record(output/'universe-validation.json',report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=Path('data/paper_archive'))
    parser.add_argument('--run-id', default='exp005-2026-10-05')
    parser.add_argument('--output', type=Path, default=Path('data/current_failure_audit'))
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--external', action='store_true')
    parser.add_argument('--universe', action='store_true')
    args = parser.parse_args()
    result = audit(args.archive, args.run_id, args.output, download=args.download)
    if args.external:
        sec = retain_url(args.output, 'sec-identities',
                         'https://www.sec.gov/files/company_tickers_exchange.json')
        print(sec)
        if sec['status']=='retained':
            import json
            from src.preservation import get_object
            identities = json.loads(get_object(args.output,sec['raw_sha256']))
            by_ticker = {r[2]:r for r in identities['data']}
            for item in result['original_failures']:
                ticker = item['ticker']
                if ticker in by_ticker:
                    cik = by_ticker[ticker][0]
                    print(retain_url(args.output, 'sec-submissions-' + ticker,
                                    f'https://data.sec.gov/submissions/CIK{cik:010d}.json'))
        for item in result['original_failures']:
            ticker = item['ticker']
            print(retain_url(args.output, 'stooq-' + ticker,
                f'https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d&d1=20160929&d2=20261005'))
        print(retain_url(args.output, 'nasdaq-ABBV',
            'https://api.nasdaq.com/api/quote/ABBV/historical?assetclass=stocks&fromdate=2019-01-11&todate=2019-01-11&limit=10'))
        print(retain_url(args.output, 'nasdaq-ABBV-range',
            'https://api.nasdaq.com/api/quote/ABBV/historical?assetclass=stocks&fromdate=2019-01-10&todate=2019-01-12&limit=10'))
    if args.universe:
        report = validate_universe(args.output, download=args.download)
        print(f'New diagnostic coverage: {report["successful"]}/{report["requested"]}')
    print(f'Original failures: {len(result["original_failures"])}; observations: '
          f'{len(result["original_observations"])}; paired: {len(result["paired_observations"])}')
