import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { getTodayWarsawIso } from './utils/dates'

function shiftIsoDays(baseIso: string, deltaDays: number): string {
  const [y, m, d] = baseIso.split('-').map(Number)
  const dt = new Date(Date.UTC(y, m - 1, d + deltaDays))
  return dt.toISOString().slice(0, 10)
}

describe('CasesPage (/cases — Spec 003)', () => {
  const today = getTodayWarsawIso()

  const sampleCases = [
    {
      id: 1,
      case_number: 'ZUS-1',
      title: 'Sprawa zaległa',
      client_name: 'Jan Kowalski',
      assigned_to: 3,
      assigned_to_email: 'trainee@example.com',
      assigned_to_is_active: true,
      deadline: shiftIsoDays(today, -2),
      date_filed: shiftIsoDays(today, -20),
      status: 'open',
      archived: false,
      version: 1,
      extra_fields: { APROBANT: 'Lewandowska' },
      created_at: '2026-11-01T08:00:00Z',
      updated_at: '2026-11-01T08:00:00Z',
    },
    {
      id: 2,
      case_number: 'ZUS-2',
      title: 'Sprawa bez terminu',
      client_name: 'Anna Nowak',
      assigned_to: 4,
      assigned_to_email: 'old@example.com',
      assigned_to_is_active: false,
      deadline: null,
      date_filed: null,
      status: 'open',
      archived: false,
      version: 1,
      extra_fields: null,
      created_at: '2026-11-02T08:00:00Z',
      updated_at: '2026-11-02T08:00:00Z',
    },
  ]

  beforeEach(() => {
    window.localStorage.clear()
    window.sessionStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('wyświetla tabelę spraw z odznakami pilności i ukrywa przycisk Nowa sprawa dla roli user', async () => {
    window.localStorage.setItem('access_token', 'user-jwt')
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.endsWith('/api/me')) {
        return new Response(
          JSON.stringify({
            id: 3,
            email: 'trainee@example.com',
            is_active: true,
            role: 'user',
            supervisor_id: 2,
            must_change_password: false,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (url.includes('/api/cases')) {
        return new Response(
          JSON.stringify({ items: [sampleCases[0]], total: 1, page: 1, page_size: 50 }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      return new Response(null, { status: 404 })
    })

    window.history.pushState({}, '', '/cases')
    render(<App />)

    expect(await screen.findByText('Sprawa zaległa')).toBeInTheDocument()
    expect(screen.getByText('ZALEGŁE')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Nowa sprawa/i })).not.toBeInTheDocument()
  })

  it('przełożony widzi nieaktywnych pracowników z etykietą (nieaktywny) i nie widzi pól dat w modalu Nowa sprawa', async () => {
    const user = userEvent.setup()
    window.localStorage.setItem('access_token', 'sup-jwt')
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.endsWith('/api/me')) {
        return new Response(
          JSON.stringify({
            id: 2,
            email: 'sup@example.com',
            is_active: true,
            role: 'supervisor',
            supervisor_id: null,
            must_change_password: false,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (url.includes('/api/users/assignable')) {
        return new Response(
          JSON.stringify([
            { id: 2, email: 'sup@example.com', role: 'supervisor', is_active: true },
            { id: 4, email: 'old@example.com', role: 'user', is_active: false },
          ]),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (url.includes('/api/cases')) {
        return new Response(
          JSON.stringify({ items: sampleCases, total: 2, page: 1, page_size: 50 }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      return new Response(null, { status: 404 })
    })

    window.history.pushState({}, '', '/cases')
    render(<App />)

    expect((await screen.findAllByText(/\(nieaktywny\)/i)).length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: /Nowa sprawa/i }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('old@example.com (nieaktywny)')).toBeInTheDocument()
    expect(within(dialog).queryByLabelText(/Termin realizacji/i)).not.toBeInTheDocument()
  })

  it('obsługuje konflikt 409 i pozwala nadpisać sprawę po konflikcie wersji', async () => {
    const user = userEvent.setup()
    window.localStorage.setItem('access_token', 'admin-jwt')

    let patchCallCount = 0
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.endsWith('/api/me')) {
        return new Response(
          JSON.stringify({
            id: 1,
            email: 'admin@example.com',
            is_active: true,
            role: 'admin',
            supervisor_id: null,
            must_change_password: false,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (url.includes('/api/users/assignable')) {
        return new Response(
          JSON.stringify([{ id: 3, email: 'trainee@example.com', role: 'user', is_active: true }]),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (url.endsWith('/api/cases/1') && init?.method === 'PATCH') {
        patchCallCount += 1
        if (patchCallCount === 1) {
          return new Response(
            JSON.stringify({
              detail: 'Konflikt wersji',
              current: { ...sampleCases[0], title: 'Wersja z serwera', version: 2 },
            }),
            { status: 409, headers: { 'Content-Type': 'application/json' } }
          )
        }
        return new Response(
          JSON.stringify({ ...sampleCases[0], status: 'closed', version: 3 }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (url.includes('/api/cases')) {
        return new Response(
          JSON.stringify({ items: [sampleCases[0]], total: 1, page: 1, page_size: 50 }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      return new Response(null, { status: 404 })
    })

    window.history.pushState({}, '', '/cases')
    render(<App />)

    const toggleBtn = await screen.findByRole('button', { name: /Zakończono: Sprawa zaległa/i })
    await user.click(toggleBtn)

    const conflictModal = await screen.findByRole('alertdialog')
    expect(within(conflictModal).getByText(/Twoja wersja/i)).toBeInTheDocument()
    expect(within(conflictModal).getByText(/Zapisana wersja/i)).toBeInTheDocument()
    expect(within(conflictModal).getAllByText(/Wersja z serwera/i).length).toBeGreaterThanOrEqual(1)

    await user.click(within(conflictModal).getByRole('button', { name: /Nadpisz/i }))
    expect(await screen.findByText(/Nadpisano sprawę Twoją wersją zmian/i)).toBeInTheDocument()
  })
})
