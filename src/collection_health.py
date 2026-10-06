"""Operational coverage history; no signal performance or outcome inspection."""

from collections import Counter
from pathlib import Path

from src.paper_archive import load_protocol, verify_run
from src.preservation import read_record
from src.prospective import protocol, verify_enrollment
from src.sessions import due_sessions, utc


def failure_category(error: str | None) -> str:
    text = (error or '').lower()
    for category, words in [('malformed_ohlc', ('malformed ohlc', 'adjustment discrepancy')),
                            ('stale_incomplete', ('stale', 'signal-date', 'incomplete', 'missing session')),
                            ('identity', ('ticker other', 'ticker does not match', 'only describe')),
                            ('duplicate', ('duplicate',)), ('missing', ('missing required', 'empty')),
                            ('schema_numeric', ('numeric', 'finite', 'timestamp', 'columns')),
                            ('acquisition', ('download', 'runtimeerror', 'oserror'))]:
        if any(word in text for word in words):
            return category
    return 'unavailable' if text else 'not_collected'


def collection_health(root: Path, *, as_of: str) -> dict:
    """Keep all 95 in the denominator, including interrupted/missing originals."""
    rules = protocol()
    config = load_protocol()
    universe = config['universe']
    due = due_sessions(rules['effective_session'], as_of)
    original = {}
    for path in (root/'runs').glob('*/intent.json'):
        intent = read_record(path)
        if (intent['mode']=='collect' and not intent['corrects']
                and intent['session'] >= rules['effective_session']
                and utc(intent['calendar']['close']) <= utc(as_of)):
            if intent['session'] in original:
                raise ValueError('Duplicate original session in health history')
            original[intent['session']] = intent
    counts = Counter()
    rows = []
    for day in sorted(set(due) | set(original)):
        intent = original.get(day)
        inputs = {}
        records = {}
        if intent:
            directory = root/'runs'/intent['run_id']
            verified = verify_run(root, intent['run_id'])
            inputs = {p.stem:read_record(p) for p in (directory/'inputs').glob('*.json')}
            if verified['status'] != 'interrupted' and (directory/'result.json').exists():
                records = {r['ticker']:r for r in read_record(directory/'result.json')['records']}
        failures = []
        success = 0
        for ticker in universe:
            record, item = records.get(ticker), inputs.get(ticker, {})
            if record and record['status']=='available':
                success += 1
            else:
                error = record.get('error') if record else item.get('error')
                category = 'not_evaluated_interrupted' if not record and item.get('status')=='available' else failure_category(error)
                failures.append({'ticker': ticker, 'session': day, 'status': 'unavailable' if item else 'not_collected',
                                 'category': category})
                if (item or record) and category != 'not_evaluated_interrupted':
                    counts[ticker] += 1
        timely = False
        if intent and (root/'exp005/receipts'/(intent['run_id']+'.json')).exists():
            enrolled = verify_enrollment(root, intent['run_id'])
            timely = set(enrolled['receipt']['classifications'])==set(universe) and all(
                c=='prospective' for c in enrolled['receipt']['classifications'].values())
        rows.append({'session': day, 'requested': len(universe), 'successful': success,
                     'collected': sum(inputs.get(t,{}).get('status')=='available' for t in universe),
                     'failed': len(universe)-success, 'coverage_percent': success/len(universe)*100,
                     'stale_incomplete': sum(f['category']=='stale_incomplete' for f in failures),
                     'complete_timely': timely, 'failures': failures,
                     'categories': dict(Counter(f['category'] for f in failures))})
    complete = sum(r['complete_timely'] and r['session'] in due for r in rows)
    streak = 0
    for row in reversed(rows):
        if not row['complete_timely']:
            break
        streak += 1
    # The registered gate is 100 scheduled sessions and >=80% complete originals.
    passed = len(due)>=100 and complete/len(due)>=.8
    return {'sessions': rows, 'recurring_failures': [{'ticker':k,'sessions':v} for k,v in sorted(counts.items())],
            'gate': {'scheduled_sessions':len(due), 'complete_timely_sessions':complete,
                     'complete_fraction': complete/len(due) if due else 0,
                     'minimum_scheduled_sessions':100, 'required_complete_fraction':.8,
                     'required_tickers_per_complete_session':len(universe), 'satisfied':passed,
                     'consecutive_valid_sessions':streak,
                     'note':'Streak is descriptive; it is not a registered acceptance criterion.'}}
