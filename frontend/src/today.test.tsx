import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import Today, { Edge, athens } from './Today'
import type { Dashboard } from './data'

it('does not substitute candidates or rates when no snapshot exists', () => {
  render(<Today data={{} as Dashboard} />)
  expect(screen.getByText('No current market snapshot')).toBeInTheDocument()
  expect(screen.queryByText('OPEN PAPER SIGNAL')).not.toBeInTheDocument()
})

it('keeps prospective performance sealed and missing Treasury rates explicit', () => {
  render(<Edge data={{} as Dashboard} />)
  expect(screen.getByText(/Insufficient prospective sample/)).toBeInTheDocument()
  expect(screen.getByText(/No reliable current rate retained/)).toBeInTheDocument()
})

it('formats operational UTC instants in Athens with daylight saving', () => {
  expect(athens('2026-10-06T13:30:00Z')).toContain('16:30')
  expect(athens('2026-11-03T14:30:00Z')).toContain('16:30')
  expect(athens(null)).toBe('Unavailable')
})

it('keeps partial coverage separate from the registered acceptance gate', () => {
  const data = {
    today: {
      clock: { as_of: '2026-10-06T12:00:00Z', market_state: 'closed' },
      snapshot: {
        session: '2026-10-05',
        rows: [],
        status: {
          expected_tickers: 95,
          successful_tickers: 72,
          failed_tickers: 23,
          completion_status: 'partial',
          classifications: {},
          signal_count: 3,
          non_event_count: 69,
        },
      },
      health: {
        sessions: [
          {
            session: '2026-10-05',
            requested: 95,
            successful: 72,
            failed: 23,
            categories: { malformed_ohlc: 23 },
          },
        ],
        recurring_failures: [{ ticker: 'ABBV', sessions: 1 }],
        gate: {
          scheduled_sessions: 0,
          complete_timely_sessions: 0,
          complete_fraction: 0,
          minimum_scheduled_sessions: 100,
          required_complete_fraction: 0.8,
          required_tickers_per_complete_session: 95,
          satisfied: false,
          consecutive_valid_sessions: 0,
          note: 'Streak is descriptive.',
        },
      },
    },
  } as unknown as Dashboard
  render(<Today data={data} />)
  expect(screen.getByText(/Coverage gate not satisfied/)).toBeInTheDocument()
  expect(
    screen.getByRole('table', { name: 'Collection reliability by session' }),
  ).toHaveTextContent('95')
  fireEvent.click(screen.getByText('Recurring failures and categories'))
  expect(screen.getByRole('table', { name: 'Failure categories' })).toHaveTextContent(
    'malformed_ohlc',
  )
  expect(screen.getByRole('table', { name: 'Recurring failing stocks' })).toHaveTextContent('ABBV')
})
