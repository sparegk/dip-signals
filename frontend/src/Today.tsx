import { useState } from 'react'
import { format, type Dashboard, type Row } from './data'
import { DataTable, Empty, Note, PageTitle, Section, type Column } from './components'
import ProspectiveValidation from './ProspectiveValidation'

export type CurrentRecord = {
  ticker: string
  status: string
  error: string | null
  retrieved_at: string | null
  latest_session: string | null
  input_hash: string | null
  features: Row | null
  volatility: Row | null
  reference: {
    cutoff_exclusive: string
    previous_events: number
    minimum_events: number
    horizons: Row[]
    volatility_horizons?: Row[]
    v1_net_ev: number | null
    v1_count: number
    average_holding_bars: number | null
    envelope: {
      count: number
      mae_quartiles: number[]
      mfe_quartiles: number[]
      median_mfe_mae_ratio: number | null
    } | null
    timing: Row[]
  } | null
}
export type TodayData = {
  health?: {
    sessions: Row[]
    recurring_failures: Row[]
    gate: {
      scheduled_sessions: number
      complete_timely_sessions: number
      complete_fraction: number
      minimum_scheduled_sessions: number
      required_complete_fraction: number
      required_tickers_per_complete_session: number
      satisfied: boolean
      consecutive_valid_sessions: number
      note: string
    }
  }
  clock: {
    as_of: string
    latest_completed_session: string
    market_state: string
    intraday_context: string
    eligible_session: string | null
    next_session: string
    next_market_open: string
    collection_window_start: string
    collection_window_end: string
  }
  warning: string | null
  snapshot: {
    session: string
    calculated_at: string
    status: Row & { classifications: Record<string, string>; code: { revision: string } }
    rows: CurrentRecord[]
    edge: Row[]
    spy: Row | null
    historical_universe_available: number
    historical_v1_count: number
    historical_v1_net_ev: number | null
    adaptive_reference: string
    treasury: Row & { scenarios?: Row[] }
  } | null
}

export function athens(value: unknown): string {
  if (typeof value !== 'string' || !value) return 'Unavailable'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Unavailable'
    : new Intl.DateTimeFormat('en-GB', {
        timeZone: 'Europe/Athens',
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(date) + ' Athens'
}
const metrics: Column[] = [
  { key: 'ticker', label: 'Ticker' },
  { key: 'signal_date', label: 'Signal session' },
  { key: 'close', label: 'Adjusted close', format: 'number' },
  {
    key: 'dip_component_count',
    label: 'Components',
    render: (r) => `${r.dip_component_count ?? '—'}/4`,
  },
  { key: 'return_1d', label: 'Daily return', format: 'percent' },
  { key: 'drawdown_20d', label: '20-bar drawdown', format: 'percent' },
  { key: 'drawdown_60d', label: '60-bar drawdown', format: 'percent' },
  { key: 'price_zscore_20d', label: 'Price z-score', format: 'number' },
  { key: 'distance_from_low_20d', label: 'Distance from low', format: 'percent' },
  { key: 'relative_return_10d', label: 'Relative weakness', format: 'percent' },
  { key: 'atr_pct_14', label: 'ATR / close', format: 'percent' },
  { key: 'relative_volume_20d', label: 'Relative volume', format: 'number' },
  { key: 'v1_net_ev', label: 'Historical reference EV', format: 'percent' },
  { key: 'historical_excess', label: 'Historical SPY excess', format: 'pp' },
  { key: 'previous_events', label: 'Prior events', format: 'integer' },
  { key: 'active_components', label: 'Active components' },
]
const horizonColumns: Column[] = [
  { key: 'horizon', label: 'Bars' },
  { key: 'count', label: 'Complete N', format: 'integer' },
  { key: 'mean', label: 'Mean gross', format: 'percent' },
  { key: 'median', label: 'Median', format: 'percent' },
  { key: 'win_rate', label: 'Win rate', format: 'rate' },
  { key: 'mfe', label: 'MFE', format: 'percent' },
  { key: 'mae', label: 'MAE', format: 'percent' },
  { key: 'spy', label: 'Matched SPY', format: 'percent' },
  { key: 'excess', label: 'Paired SPY excess', format: 'pp' },
  { key: 'paired_count', label: 'Paired N', format: 'integer' },
  { key: 'spy_median', label: 'Matched SPY median', format: 'percent' },
  { key: 'status', label: 'History status' },
]

function flat(record: CurrentRecord): Row {
  const ten = record.reference?.horizons.find((r) => r.horizon === 10)
  return {
    ticker: record.ticker,
    status: record.status,
    error: record.error,
    ...record.features,
    active_components: record.features
      ? [
          ['dip_drawdown_component', 'Drawdown'],
          ['dip_price_zscore_component', 'Z-score'],
          ['dip_low_proximity_component', 'Low proximity'],
          ['dip_relative_weakness_component', 'Relative weakness'],
        ]
          .filter(([key]) => record.features?.[key])
          .map(([, label]) => label)
          .join(', ') || 'None'
      : null,
    v1_net_ev: record.reference?.v1_net_ev ?? null,
    historical_excess: ten?.excess ?? null,
    previous_events: record.reference?.previous_events ?? null,
  }
}

function SignalDetail({ record, today }: { record: CurrentRecord; today: TodayData }) {
  const snapshot = today.snapshot!
  const ref = record.reference
  const fields = [
    ['drawdown_60d', 'dip_drawdown_component', '60-bar drawdown'],
    ['price_zscore_20d', 'dip_price_zscore_component', 'Price z-score'],
    ['distance_from_low_20d', 'dip_low_proximity_component', 'Distance from recent low'],
    ['relative_return_10d', 'dip_relative_weakness_component', 'Relative weakness'],
  ]
  const isProspective = snapshot.status.classifications[record.ticker] === 'prospective'
  return (
    <div className="signal-detail" aria-label={`${record.ticker} signal detail`}>
      <Section
        title={`Signal Detail · ${record.ticker}`}
        note="Paper research candidate — not a trade recommendation."
      >
        <Note>
          {isProspective
            ? 'OPEN PAPER SIGNAL · original prospective decision'
            : 'Current Market Snapshot · not enrolled prospective evidence'}
          . Historical reference only — current future outcome is unknown.
        </Note>
        <dl className="today-facts">
          <div>
            <dt>Signal session</dt>
            <dd>{snapshot.session}</dd>
          </div>
          <div>
            <dt>Decision publication</dt>
            <dd>{athens(snapshot.status.collection_completed)}</dd>
          </div>
          <div>
            <dt>Source retrieved</dt>
            <dd>{athens(record.retrieved_at)}</dd>
          </div>
          <div>
            <dt>Observed entry timestamp</dt>
            <dd>Unknown — future entry is not a recorded fill</dd>
          </div>
          <div>
            <dt>Expected entry opportunity</dt>
            <dd>{athens(snapshot.status.expected_entry_timestamp)}</dd>
          </div>
          <div>
            <dt>Adjusted close</dt>
            <dd>{format(record.features?.close, 'number')}</dd>
          </div>
          <div>
            <dt>Volume</dt>
            <dd>
              {format(record.features?.volume, 'integer')} · relative{' '}
              {format(record.features?.relative_volume_20d, 'number')}
            </dd>
          </div>
          <div>
            <dt>SPY / volatility context</dt>
            <dd>
              {String(snapshot.spy?.regime ?? 'Unavailable')} ·{' '}
              {String(record.volatility?.group ?? 'Unavailable')}
            </dd>
          </div>
          <div>
            <dt>Prior ATR boundaries</dt>
            <dd>
              {format(record.volatility?.lower)} / {format(record.volatility?.upper)}
            </dd>
          </div>
        </dl>
        <DataTable
          caption="Why the V1 event triggered"
          rows={fields.map(([feature, component, name]) => ({
            component: name,
            value: record.features?.[feature] ?? null,
            threshold: record.features?.[`${feature}_threshold`] ?? null,
            active: record.features?.[component] ?? false,
          }))}
          columns={[
            { key: 'component', label: 'Component' },
            { key: 'value', label: 'Value', format: 'number' },
            { key: 'threshold', label: 'Prior 20th-percentile threshold', format: 'number' },
            { key: 'active', label: 'Active (value ≤ threshold)' },
          ]}
        />
        <p>
          V1 requires complete measurements and at least three active components. An event is the
          rising edge of this condition.
        </p>
        <details>
          <summary>Reproducibility</summary>
          <p>
            Input SHA-256: {record.input_hash}. Configuration:{' '}
            {String(snapshot.status.configuration_hash)}. Code revision:{' '}
            {snapshot.status.code.revision}.
          </p>
        </details>
      </Section>
      <Section
        title="Historical Context"
        note={`Same-ticker reference; all windows end before ${ref?.cutoff_exclusive ?? 'the signal'}. Adjusted vintage, not point-in-time historical prices.`}
      >
        {!ref || ref.horizons.every((r) => r.status !== 'available') ? (
          <Note>Insufficient same-ticker history</Note>
        ) : null}
        <p>
          Historical reference EV: {format(ref?.v1_net_ev)} net under the historical V1 control
          across {ref?.v1_count ?? 0} mature prior events. Mean control holding time:{' '}
          {format(ref?.average_holding_bars, 'number')} observed bars.
        </p>
        <DataTable
          caption="Same-ticker historical forward references"
          rows={ref?.horizons ?? []}
          columns={horizonColumns}
        />
        <details className="disclosure">
          <summary>Historical events in the current volatility group</summary>
          <p>
            Descriptive context only. Each prior event uses its own prior ATR tertiles. Subgroups
            also require 20 completed events per horizon.
          </p>
          <DataTable
            caption="Same-ticker historical volatility context"
            rows={
              ref?.volatility_horizons?.filter((r) => r.group === record.volatility?.group) ?? []
            }
            columns={horizonColumns}
          />
        </details>
        <p>
          Broader-universe historical V1 reference EV: {format(snapshot.historical_v1_net_ev)} net
          across {snapshot.historical_v1_count} mature events. This is a separate cross-sectional
          sample, with survivor selection and overlapping events.
        </p>
        <DataTable
          caption="Broader cross-sectional reference"
          rows={snapshot.edge}
          columns={horizonColumns.filter((c) => c.key !== 'status')}
        />
      </Section>
      <Section
        title="Exit Research Envelope"
        note="Descriptive historical ranges, not an optimal exit or a stop recommendation."
      >
        <p>
          One ATR distance: {format(record.features?.atr_14, 'number')} adjusted price units ·{' '}
          {format(record.features?.atr_pct_14)} of close.
        </p>
        {ref?.envelope ? (
          <>
            <DataTable
              caption="Prior ten-bar excursion quartiles"
              rows={['25th', '50th', '75th'].map((q, i) => ({
                percentile: q,
                mae: ref.envelope!.mae_quartiles[i],
                mfe: ref.envelope!.mfe_quartiles[i],
              }))}
              columns={[
                { key: 'percentile', label: 'Percentile' },
                { key: 'mae', label: 'Historical MAE', format: 'percent' },
                { key: 'mfe', label: 'Historical MFE', format: 'percent' },
              ]}
            />
            <p>
              N = {ref.envelope.count}. Ratio of median MFE to median absolute MAE:{' '}
              {format(ref.envelope.median_mfe_mae_ratio, 'number')}. Signed return quartiles: more
              negative MAE means more adverse movement.
            </p>
          </>
        ) : (
          <Note>Insufficient same-ticker history for the exit envelope.</Note>
        )}
        <DataTable
          caption="Historical twenty-bar rebound timing"
          rows={ref?.timing ?? []}
          columns={[
            { key: 'level', label: 'Rebound (%)' },
            { key: 'complete_paths', label: 'Complete paths' },
            { key: 'reached', label: 'Reached' },
            { key: 'median_bars_if_reached', label: 'Median bars among hits', format: 'number' },
          ]}
        />
        <p>Non-hits remain in the complete-path denominator. {snapshot.adaptive_reference}.</p>
        <p>
          Ten-bar hold is the simple comparison. The 7% stop / 10% target is only the historical V1
          control; neither is a validated final strategy.
        </p>
      </Section>
    </div>
  )
}

export default function Today({
  data,
  signalsOnly = false,
}: {
  data: Dashboard
  signalsOnly?: boolean
}) {
  const [selected, setSelected] = useState('')
  const [components, setComponents] = useState('all')
  const today = data.today
  const snapshot = today?.snapshot
  const candidates =
    snapshot?.rows.filter((r) => r.status === 'available' && r.features?.dip_event_v1) ?? []
  const detail = candidates.find((r) => r.ticker === selected)
  return (
    <>
      <PageTitle
        eyebrow="Current Market Snapshot"
        title={signalsOnly ? 'Current Dip Candidates' : 'Today'}
      >
        Completed daily bars · frozen V1 · paper research. Future outcomes remain unknown.
      </PageTitle>
      {today ? (
        <Section
          title="Collection status"
          note={`Market state as of ${athens(today.clock.as_of)} · ${today.clock.market_state}`}
        >
          <dl className="today-facts">
            <div>
              <dt>Latest completed US session</dt>
              <dd>{today.clock.latest_completed_session}</dd>
            </div>
            <div>
              <dt>Latest eligible session</dt>
              <dd>{today.clock.eligible_session ?? 'Outside prospective collection window'}</dd>
            </div>
            <div>
              <dt>Collected session / publication</dt>
              <dd>
                {snapshot?.session ?? 'Unavailable'} ·{' '}
                {athens(snapshot?.status.collection_completed)}
              </dd>
            </div>
            <div>
              <dt>Collection status</dt>
              <dd>{String(snapshot?.status.completion_status ?? 'Not collected')}</dd>
            </div>
            <div>
              <dt>Next collection window</dt>
              <dd>
                {athens(today.clock.collection_window_start)} →{' '}
                {athens(today.clock.collection_window_end)}
              </dd>
            </div>
            <div>
              <dt>Next market session / open</dt>
              <dd>
                {today.clock.next_session} · {athens(today.clock.next_market_open)}
              </dd>
            </div>
          </dl>
          <p>
            {today.clock.intraday_context}. Operational times use Europe/Athens; UTC is retained
            internally.
          </p>
          <p>
            This is a saved snapshot, not an auto-updating feed. Run{' '}
            <code>python -m scripts.run_today</code> and reload to refresh.
          </p>
          {today.warning && <Note warning>{today.warning}</Note>}
          {snapshot && snapshot.status.completion_status !== 'complete' && (
            <Note warning>
              Partial collection — {String(snapshot.status.failed_tickers)} requested stocks
              unavailable. This run does not satisfy the all-name prospective coverage gate.
            </Note>
          )}
        </Section>
      ) : null}
      {!snapshot ? (
        <Empty title="No current market snapshot">
          Run <code>python -m scripts.run_today</code> from the project environment.
        </Empty>
      ) : (
        <>
          <Section
            title="Current V1 candidates"
            note="Only rising-edge V1 events are candidates. Paper research candidate — not a trade recommendation."
          >
            <DataTable
              caption="Current V1 candidates"
              rows={candidates.map((r) => ({ ...flat(r), signal_date: snapshot.session }))}
              columns={metrics}
              onSelect={(r) => setSelected(String(r.ticker))}
            />
            {candidates.length === 0 && (
              <Note>
                No V1 events in the available completed-session observations. Missing stocks remain
                unknown.
              </Note>
            )}
          </Section>
          <Section title="Universe health" note={String(snapshot.status.data_source)}>
            <p>
              {String(snapshot.status.expected_tickers)} requested ·{' '}
              {String(snapshot.status.successful_tickers)} evaluated ·{' '}
              {String(snapshot.status.failed_tickers)} failed ·{' '}
              {String(snapshot.status.signal_count)} events ·{' '}
              {String(snapshot.status.non_event_count)} non-events.
            </p>
            <DataTable
              caption="Unavailable requested stocks"
              rows={snapshot.rows
                .filter((r) => r.status !== 'available')
                .map((r) => ({
                  ticker: r.ticker,
                  status: r.status,
                  reason: r.error,
                  latest_session: r.latest_session,
                  signal_session: snapshot.session,
                }))}
              columns={[
                { key: 'ticker', label: 'Ticker' },
                { key: 'status', label: 'Status' },
                { key: 'signal_session', label: 'Requested session' },
                { key: 'latest_session', label: 'Latest source session' },
                { key: 'reason', label: 'Unavailable — reason' },
              ]}
            />
          </Section>
          {today?.health && (
            <Section
              title="Prospective Coverage Gate"
              note="Operational reliability only; no signal performance."
            >
              <p>
                {today.health.gate.complete_timely_sessions}/{today.health.gate.scheduled_sessions}{' '}
                complete timely sessions
                {' · '}
                {format(today.health.gate.complete_fraction, 'rate')} coverage of scheduled
                sessions. Required: at least {today.health.gate.minimum_scheduled_sessions}{' '}
                scheduled sessions, {format(today.health.gate.required_complete_fraction, 'rate')}{' '}
                complete timely originals, with all{' '}
                {today.health.gate.required_tickers_per_complete_session} requested stocks each
                time.
              </p>
              <Note warning={!today.health.gate.satisfied}>
                {today.health.gate.satisfied
                  ? 'Operational coverage gate satisfied; registered review date still applies.'
                  : 'Coverage gate not satisfied.'}{' '}
                Consecutive valid sessions: {today.health.gate.consecutive_valid_sessions}.{' '}
                {today.health.gate.note}
              </Note>
              <DataTable
                caption="Collection reliability by session"
                rows={today.health.sessions}
                columns={[
                  { key: 'session', label: 'Session' },
                  { key: 'requested', label: 'Requested' },
                  { key: 'collected', label: 'Collected inputs' },
                  { key: 'successful', label: 'Successfully evaluated' },
                  { key: 'failed', label: 'Failed / not collected' },
                  { key: 'stale_incomplete', label: 'Stale / incomplete' },
                  { key: 'coverage_percent', label: 'Coverage (%)', format: 'number' },
                  { key: 'complete_timely', label: 'Complete timely original' },
                ]}
              />
              <details className="disclosure">
                <summary>Recurring failures and categories</summary>
                <DataTable
                  caption="Recurring failing stocks"
                  rows={today.health.recurring_failures}
                  columns={[
                    { key: 'ticker', label: 'Ticker' },
                    { key: 'sessions', label: 'Failed sessions' },
                  ]}
                />
                <DataTable
                  caption="Failure categories"
                  rows={today.health.sessions.flatMap((r) =>
                    Object.entries((r.categories ?? {}) as Record<string, number>).map(
                      ([category, count]) => ({ session: r.session, category, count }),
                    ),
                  )}
                  columns={[
                    { key: 'session', label: 'Session' },
                    { key: 'category', label: 'Category' },
                    { key: 'count', label: 'Stocks' },
                  ]}
                />
              </details>
            </Section>
          )}
          <Section
            title="Current market context"
            note="SPY is the equity benchmark; no separate intraday S&P 500 feed is implied."
          >
            <p>
              SPY adjusted close {format(snapshot.spy?.close, 'number')} · daily return{' '}
              {format(snapshot.spy?.return_1d)} · ATR/close {format(snapshot.spy?.atr_pct_14)} ·{' '}
              {String(snapshot.spy?.regime ?? 'Unavailable')}.
            </p>
            <p>
              V1 condition breadth:{' '}
              {snapshot.rows.filter((r) => r.features?.dip_condition_v1).length} /{' '}
              {String(snapshot.status.successful_tickers)} evaluated stocks. This is component
              context, not a new signal.
            </p>
          </Section>
          {detail && <SignalDetail record={detail} today={today!} />}
          <details className="disclosure">
            <summary>Signal Monitor · entire 95-name universe</summary>
            <label>
              Active components{' '}
              <select
                aria-label="Active components"
                value={components}
                onChange={(e) => setComponents(e.target.value)}
              >
                <option value="all">All observations</option>
                {[0, 1, 2, 3, 4].map((n) => (
                  <option key={n} value={n}>
                    {n}/4
                  </option>
                ))}
              </select>
            </label>
            <DataTable
              caption="Current universe signal monitor"
              rows={snapshot.rows
                .filter(
                  (r) =>
                    components === 'all' || r.features?.dip_component_count === Number(components),
                )
                .map(flat)}
              columns={[
                ...metrics,
                { key: 'dip_condition_v1', label: 'V1 condition' },
                { key: 'dip_event_v1', label: 'V1 event' },
                { key: 'status', label: 'Status' },
                { key: 'error', label: 'Failure reason' },
              ]}
            />
          </details>
        </>
      )}
      <Section
        title="Prospective archive progress"
        note="Prospective Evidence · operational counts only until the registered review."
      >
        <p>
          Select a ticker for details. Sort by a column heading; scroll sideways for all
          measurements.
        </p>
        <p>
          {data.prospective?.events ?? 0} genuine events · {data.prospective?.pending_outcomes ?? 0}{' '}
          pending ten-bar paired outcomes · {data.prospective?.completed_outcomes ?? 0} complete
          paired outcome records.
        </p>
        <p>
          {data.prospective?.complete_runs ?? 0} complete timely runs /{' '}
          {data.prospective?.scheduled_sessions ?? 0} due sessions. Next review:{' '}
          {data.prospective?.protocol.review_dates[0] ?? 'Unavailable'}.
        </p>
        <a href="#edge">Open Edge Monitor and Prospective Edge →</a>
      </Section>
    </>
  )
}

export function Edge({ data }: { data: Dashboard }) {
  const snapshot = data.today?.snapshot
  return (
    <>
      <PageTitle eyebrow="Historical Reference / Prospective Evidence" title="Edge Monitor">
        Incremental return over alternatives matters more than positive absolute returns.
      </PageTitle>
      <Section
        title="Historical Reference"
        note="Pre-EXP-005 history only. This recomputed descriptive vintage is separate from frozen experiment results."
      >
        <p>
          {snapshot?.historical_universe_available ?? 0} / 95 requested names available. Adjusted
          revisions, static survivor universe, missing names and dependent overlapping observations
          limit interpretation.
        </p>
        <DataTable
          caption="Historical edge comparisons"
          rows={snapshot?.edge ?? []}
          columns={[
            ...horizonColumns.filter((c) => !['status', 'win_rate', 'mfe', 'mae'].includes(c.key)),
            { key: 'non_signal', label: 'Non-signal mean', format: 'percent' },
            { key: 'non_signal_median', label: 'Non-signal median', format: 'percent' },
            { key: 'non_signal_count', label: 'Non-signal N' },
            { key: 'difference_non_signal', label: 'Difference vs non-signal', format: 'pp' },
            { key: 'unconditional', label: 'Unconditional mean', format: 'percent' },
            { key: 'unconditional_median', label: 'Unconditional median', format: 'percent' },
            { key: 'unconditional_count', label: 'Unconditional N' },
          ]}
        />
        <p>
          Gross next-observed-open to horizon-close returns. SPY excess is paired at exact
          endpoints; non-signal and unconditional differences are descriptive unmatched comparisons,
          not causal effects.
        </p>
      </Section>
      <Section
        title="Lower-risk opportunity cost"
        note="Current yield scenario — not a historical Treasury excess calculation or a Treasury total-return strategy."
      >
        <p>
          13-week Treasury annual investment yield: {format(snapshot?.treasury.annual_yield)} ·
          quote date {String(snapshot?.treasury.rate_date ?? 'Unavailable')} · retrieved{' '}
          {athens(snapshot?.treasury.retrieved_at)}.
        </p>
        {snapshot?.treasury.status !== 'available' && (
          <Note>
            Unavailable — {String(snapshot?.treasury.error ?? 'No reliable current rate retained')}.
          </Note>
        )}
        <DataTable
          caption="Current Treasury holding-period scenarios"
          rows={snapshot?.treasury.scenarios ?? []}
          columns={[
            { key: 'horizon', label: 'Observed bars' },
            { key: 'entry_session', label: 'Expected entry' },
            { key: 'exit_session', label: 'Expected endpoint' },
            { key: 'return', label: 'Cash opportunity cost', format: 'percent' },
          ]}
        />
        <p>
          Annual yield × actual calendar-day fractions (365/366), held constant. Equities carry
          substantially different downside; these are distinct risk exposures.
        </p>
        <a href="https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_bill_rates">
          Official Treasury source →
        </a>
      </Section>
      <Section
        title="Prospective Edge"
        note="Registered reviews control access to performance, including individual returns."
      >
        {!data.prospective?.review && (
          <Note>
            Insufficient prospective sample — evidence pending. Accumulating returns remain sealed
            until the registered review gate.
          </Note>
        )}
        <p>
          SPY, non-signal, unconditional and decision-time cash comparisons require mature linked
          vintages. Adaptive outcome: unavailable until a single policy is pre-registered. Portfolio
          drawdown: unavailable until allocation is registered.
        </p>
        {data.prospective?.benchmark_review && (
          <DataTable
            caption="Registered prospective benchmark review"
            rows={data.prospective.benchmark_review.tables}
            columns={[
              { key: 'horizon', label: 'Bars' },
              { key: 'selection', label: 'Selection' },
              { key: 'count', label: 'N' },
              { key: 'mean', label: 'Gross mean', format: 'percent' },
              { key: 'median', label: 'Median', format: 'percent' },
              { key: 'net_mean', label: 'Net mean', format: 'percent' },
              { key: 'spy_excess', label: 'Paired gross SPY excess', format: 'pp' },
              { key: 'spy_paired_count', label: 'SPY paired N' },
              { key: 'cash', label: 'Cash proxy', format: 'percent' },
              { key: 'cash_excess', label: 'Net excess vs cash', format: 'pp' },
              { key: 'cash_paired_count', label: 'Cash paired N' },
            ]}
          />
        )}
      </Section>
      <ProspectiveValidation data={data} />
    </>
  )
}
