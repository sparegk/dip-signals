import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import type { Dashboard } from './data'
import ProspectiveValidation from './ProspectiveValidation'

const empty = {
  documents: {},
  prospective: {
    protocol: { effective_session: '2026-10-05', review_dates: ['2027-04-01', '2027-10-01'] },
    days_collected: 0,
    genuine_records: 0,
    events: 0,
    non_events: 0,
    failures: 0,
    requested_count: 95,
    completed_outcomes: 0,
    pending_outcomes: 0,
    scheduled_sessions: 0,
    complete_runs: 0,
    latest_collection: null,
    comparison: [],
    records: [],
  },
} as unknown as Dashboard

it('shows honest empty evidence and locked comparisons', () => {
  render(<ProspectiveValidation data={empty} />)
  expect(
    screen.getByText('Prospective validation has not started producing outcome evidence yet.'),
  ).toBeInTheDocument()
  expect(screen.getByText(/awaiting first eligible completed session/)).toBeInTheDocument()
  expect(screen.getByText(/Performance sealed/)).toBeInTheDocument()
})

it('keeps replay out of latest paper signals and filters events without changing data', () => {
  const records = [
    {
      ticker: 'ABT',
      session: '2026-10-05',
      classification: 'prospective',
      status: 'available',
      published_at: '2026-10-06T12:00:00Z',
      values: { dip_event_v1: true, dip_ready_v1: true, dip_component_count: 3 },
      volatility: { group: 'low', atr_close: 0.015 },
    },
    {
      ticker: 'BMY',
      session: '2026-10-05',
      classification: 'prospective',
      status: 'available',
      published_at: '2026-10-06T12:00:00Z',
      values: { dip_event_v1: false, dip_ready_v1: true, dip_component_count: 1 },
    },
    {
      ticker: 'REPLAY',
      session: '2026-10-05',
      classification: 'retrospective',
      status: 'available',
      values: { dip_event_v1: true },
    },
  ]
  const data = {
    ...empty,
    prospective: { ...empty.prospective!, records, genuine_records: 2, events: 1 },
  } as unknown as Dashboard
  render(<ProspectiveValidation data={data} />)
  expect(screen.getByText('ABT')).toBeInTheDocument()
  expect(screen.getByText('BMY')).toBeInTheDocument()
  fireEvent.click(screen.getByLabelText('Events only'))
  expect(screen.queryByText('BMY')).not.toBeInTheDocument()
  expect(records.length).toBe(3)
  expect(screen.getByText(/no orders are placed/)).toBeInTheDocument()
})

it('handles missing operational exports', () => {
  render(<ProspectiveValidation data={{} as Dashboard} />)
  expect(screen.getByText(/Export EXP-005/)).toBeInTheDocument()
})
