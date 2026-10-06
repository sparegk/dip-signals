"""Hash-verified historical loss diagnosis; no prospective outcome reads."""

import json
from pathlib import Path

import pandas as pd

from src.loss_diagnostics import diagnose_losses
from src.preservation import digest, write_record


def run() -> dict:
    source = Path('results/exp_002')
    metadata = json.loads((source/'metadata.json').read_bytes())
    for name, expected in metadata['artifact_sha256'].items():
        if Path(name).name != name or digest((source/name).read_bytes()) != expected:
            raise ValueError(f'Frozen artifact changed: {name}')
    tables = diagnose_losses(pd.read_parquet(source/'observations.parquet'),
                             pd.read_parquet(source/'trades.parquet'), cutoff='2026-10-05')
    output = Path('data/loss_diagnostics_v2')
    output.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name, frame in tables.items():
        content = frame.to_csv(index=False, float_format='%.17g').encode()
        from src.preservation import publish
        publish(output/f'{name}.csv', content)
        hashes[name] = digest(content)
    e = tables['events']
    mature = e.loc[e.observed_bars.eq(20)]
    stopped = mature.loc[mature.stop_out]
    summary = {'status': 'consumed_historical_diagnosis_only', 'cutoff_exclusive': '2026-10-05',
        'events': len(e), 'complete_20bar_paths': len(mature), 'stops_with_20bar_path': len(stopped),
        'recover_after_stop': int(stopped.recovered_after_stop_bar.notna().sum()),
        'median_recovery_bar_after_stop': float(stopped.recovered_after_stop_bar.median()),
        'gap_stops': int(e.gap_stop.sum()), 'all_stops': int(e.stop_out.sum()),
        'loss_categories': mature.loc[mature.control_net_return.le(0)].recovery_category.value_counts().to_dict(),
        'artifacts': hashes, 'source_artifacts': metadata['artifact_sha256'],
        'source_hashes': {p:digest(Path(p).read_bytes().replace(b'\r\n',b'\n')) for p in
                          ['src/loss_diagnostics.py','scripts/diagnose_losses.py']},
        'limitations': ['Consumed history; no predictors fitted or stops selected',
                       'Daily bars cannot order intraday highs/lows', 'Dependence, survivor universe and adjusted vintages',
                       '20-bar non-recovery is censoring, not never recovering', 'No portfolio drawdown methodology']}
    write_record(output/'summary.json', summary)
    return summary


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
