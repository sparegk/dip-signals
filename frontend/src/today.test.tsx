import { render, screen } from '@testing-library/react'
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
