import { useState } from 'react'
import { DataTable, Disclosure, Metric, Note, PageTitle, Section } from './components'
import { type Dashboard, type Row } from './data'
import { Document, Missing } from './Research'

export default function ProspectiveValidation({ data }: { data: Dashboard }) {
  const [eventsOnly, setEventsOnly] = useState(false)
  const p = data.prospective
  if (!p) return <Missing reason="Export EXP-005 operational data to initialize this view." />
  const latest = p.records.reduce((day, r) => (r.session > day ? r.session : day), '')
  const rows: Row[] = p.records
    .filter(
      (r) =>
        r.session === latest &&
        r.classification === 'prospective' &&
        (!eventsOnly || r.values?.dip_event_v1 === true),
    )
    .map((r) => ({
      ticker: r.ticker,
      session: r.session,
      event: r.values?.dip_event_v1 ?? null,
      ready: r.values?.dip_ready_v1 ?? null,
      components: r.values?.dip_component_count ?? null,
      drawdown: r.values?.drawdown_60d ?? null,
      zscore: r.values?.price_zscore_20d ?? null,
      relative: r.values?.relative_return_10d ?? null,
      atr: r.volatility?.atr_close ?? null,
      volatility: r.volatility?.group ?? 'unavailable',
      recorded: r.published_at,
    }))
  const failures: Row[] = p.records
    .filter((r) => r.session === latest && r.classification !== 'prospective')
    .map((r) => ({
      ticker: r.ticker,
      status: r.status,
      error: r.error,
      classification: r.classification,
    }))
  return (
    <>
      <PageTitle eyebrow="EXP-005 · Registered prospective test" title="Prospective Validation">
        Same V1 signals. Fixed historical exit versus a ten-bar hold. No tuning.
      </PageTitle>
      <Note warning>
        {p.completed_outcomes === 0
          ? 'Prospective validation has not started producing outcome evidence yet.'
          : 'Outcomes are preserved separately. Performance is shown only at registered reviews.'}
      </Note>
      <div className="metric-grid">
        {[
          ['Days collected', p.days_collected, 'Actual enrolled sessions'],
          ['Genuine records', p.genuine_records, 'Includes non-events; excludes replay'],
          ['Events', p.events, 'Original V1 rising-edge signals'],
          ['Completed outcomes', p.completed_outcomes, 'Full ten-bar paired windows'],
          ['Pending outcomes', p.pending_outcomes, 'Events awaiting ten completed bars'],
          ['Requested tickers', p.requested_count, 'Frozen EXP-003 list'],
          ['Non-events', p.non_events, 'Preserved alongside signals'],
          ['Excluded records', p.failures, 'Failed inputs or invalid timing'],
        ].map(([label, value, note]) => (
          <Metric
            key={String(label)}
            label={String(label)}
            value={value}
            kind="integer"
            note={String(note)}
          />
        ))}
      </div>
      <Section title="Collection status">
        <p>
          Effective session: {p.protocol.effective_session}. Last collection:{' '}
          {p.latest_collection ?? 'None'}.
        </p>
        <p>
          {p.complete_runs} complete runs across {p.scheduled_sessions} due sessions. A failed run
          is kept.
        </p>
        <p>
          {p.failed_collections ?? 0} incomplete collection attempts;{' '}
          {p.missing_sessions?.length ?? 0} missing sessions.
        </p>
        {!!p.incomplete_runs?.length && (
          <DataTable
            caption="Incomplete collection attempts, excluded from evidence"
            rows={p.incomplete_runs}
            columns={[
              { key: 'run_id', label: 'Run' },
              { key: 'session', label: 'Session' },
              { key: 'status', label: 'Status' },
            ]}
          />
        )}
      </Section>
      <Section
        title="Paper signal lifecycle"
        note="Maturity counts only. Individual returns remain sealed."
      >
        <DataTable
          caption="Prospective horizon maturity"
          rows={[1, 3, 5, 10, 20].map((h) => ({
            horizon: h,
            completed: p.horizon_completion?.[String(h)] ?? 0,
            pending: p.events - (p.horizon_completion?.[String(h)] ?? 0),
          }))}
          columns={[
            { key: 'horizon', label: 'Bars' },
            { key: 'completed', label: 'Completed horizons' },
            { key: 'pending', label: 'Pending / unavailable' },
          ]}
        />
      </Section>
      <Section title="Latest Paper Signals" note="Paper research only — no orders are placed.">
        {!p.genuine_records ? (
          <p>Prospective archive initialized — awaiting first eligible completed session.</p>
        ) : (
          <>
            <label>
              <input
                type="checkbox"
                checked={eventsOnly}
                onChange={(e) => setEventsOnly(e.target.checked)}
              />{' '}
              Events only
            </label>
            <DataTable
              caption="Latest enrolled session: genuine prospective observations"
              rows={rows}
              columns={[
                { key: 'ticker', label: 'Ticker' },
                { key: 'session', label: 'Session' },
                { key: 'event', label: 'Event' },
                { key: 'ready', label: 'Ready' },
                { key: 'components', label: 'Components', format: 'integer' },
                { key: 'drawdown', label: 'Drawdown', format: 'percent' },
                { key: 'zscore', label: 'Z-score', format: 'number' },
                { key: 'relative', label: 'Relative return', format: 'percent' },
                { key: 'atr', label: 'ATR / close', format: 'percent' },
                { key: 'volatility', label: 'Volatility group' },
                { key: 'recorded', label: 'Recorded UTC' },
              ]}
            />
          </>
        )}
        {failures.length > 0 && (
          <Disclosure title="Missing data and excluded decisions">
            <DataTable
              caption="Excluded observations remain visible"
              rows={failures}
              columns={[
                { key: 'ticker', label: 'Ticker' },
                { key: 'status', label: 'Status' },
                { key: 'classification', label: 'Timing' },
                { key: 'error', label: 'Reason' },
              ]}
            />
          </Disclosure>
        )}
      </Section>
      <Section title="What are we comparing?">
        <DataTable
          caption="Frozen same-entry exit comparison"
          rows={[
            { policy: 'Historical V1 exit control', stop: '7%', target: '10%', timeout: '10 bars' },
            { policy: 'Ten-bar hold', stop: 'None', target: 'None', timeout: '10 bars' },
          ]}
          columns={[
            { key: 'policy', label: 'Exit policy' },
            { key: 'stop', label: 'Stop' },
            { key: 'target', label: 'Target' },
            { key: 'timeout', label: 'Timeout' },
          ]}
        />
        <p>
          Next observed open entry; 1 bp commission + 5 bp slippage per side. The control is not
          optimal by assumption.
        </p>
      </Section>
      <Section
        title="Prospective comparison"
        note="EV, win rate and downside are separate measures."
      >
        {!p.comparison.length ? (
          <p>
            Performance sealed until a registered review: {p.protocol.review_dates.join(' or ')}.
            Coverage must also pass. No fabricated charts or daily performance peeking.
          </p>
        ) : (
          <DataTable
            caption="Registered review: net trade statistics, not portfolio returns"
            rows={p.comparison}
            columns={[
              { key: 'policy', label: 'Policy' },
              { key: 'grouping', label: 'Breakdown' },
              { key: 'group', label: 'Group' },
              { key: 'trade_count', label: 'Trades', format: 'integer' },
              { key: 'expected_value', label: 'Net EV', format: 'percent' },
              { key: 'median_return', label: 'Median', format: 'percent' },
              { key: 'win_rate', label: 'Win rate', format: 'rate' },
              { key: 'average_win', label: 'Mean win', format: 'percent' },
              { key: 'average_loss', label: 'Mean loss', format: 'percent' },
              { key: 'profit_factor', label: 'Profit factor', format: 'number' },
              { key: 'average_mfe', label: 'MFE', format: 'percent' },
              { key: 'average_mae', label: 'MAE', format: 'percent' },
              { key: 'fifth_percentile', label: '5th percentile', format: 'percent' },
            ]}
          />
        )}
      </Section>
      {p.review && (
        <Section
          title="Rebound duration and benchmark comparison"
          note="Gross event returns; exact paired SPY windows. Missing benchmarks stay missing."
        >
          <DataTable
            caption="Registered forward-horizon review"
            rows={p.review.forward}
            columns={[
              { key: 'horizon', label: 'Bars', format: 'integer' },
              { key: 'group', label: 'Volatility group' },
              { key: 'count', label: 'Complete events', format: 'integer' },
              { key: 'mean', label: 'Mean return', format: 'percent' },
              { key: 'median', label: 'Median', format: 'percent' },
              { key: 'matched_spy_excess', label: 'Matched-SPY excess', format: 'pp' },
              { key: 'mfe', label: 'MFE', format: 'percent' },
              { key: 'mae', label: 'MAE', format: 'percent' },
            ]}
          />
          <p>
            Reviewed {p.review.reviewed_at}. Events can overlap; subgroup differences are
            descriptive.
          </p>
        </Section>
      )}
      <Disclosure title="Protocol and daily commands">
        <Document body={data.documents.EXP005_PROTOCOL ?? 'Protocol unavailable.'} />
      </Disclosure>
    </>
  )
}
