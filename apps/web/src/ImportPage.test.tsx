import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

describe('ImportPage (/import — Spec 004)', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.sessionStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('użytkownik nie-admin widzi przycisk kopii bieżących spraw bez uploadu i ma zablokowane pola dat', async () => {
    const user = userEvent.setup()
    window.localStorage.setItem('access_token', 'user-jwt')

    const snapshotDetail = {
      id: 10,
      source_type: 'snapshot',
      label: 'Kopia bieżących spraw',
      row_count: 1,
      error_count: 0,
      conflict_count: 0,
      created_at: '2026-11-24T10:00:00Z',
      expires_at: '2026-11-25T10:00:00Z',
      rows: [
        {
          row_index: 2,
          case_id: 1,
          version: 1,
          case_number: 'ZUS-1',
          title: 'Sprawa testowa',
          client_name: 'Jan Kowalski',
          assigned_to_email: 'trainee@example.com',
          deadline: '2027-01-15',
          date_filed: '2026-11-01',
          status: 'open',
          note: null,
          extra_columns: { APROBANT: 'Lewandowska' },
          errors: [],
          warnings: [],
          conflict: false,
          resolution: null,
        },
      ],
    }

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
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
      if (url.endsWith('/api/import/copies') && (!init?.method || init.method === 'GET')) {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.endsWith('/api/import/copies/from-cases') && init?.method === 'POST') {
        return new Response(JSON.stringify(snapshotDetail), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      return new Response(null, { status: 404 })
    })

    window.history.pushState({}, '', '/import')
    render(<App />)

    expect(
      await screen.findByRole('heading', { name: /Edytor pliku Excel/i })
    ).toBeInTheDocument()
    expect(screen.queryByLabelText(/Wgraj plik Excel/i)).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Otwórz kopię bieżących spraw/i }))

    const deadlineInput = await screen.findByLabelText(/Termin wiersz 2/i)
    expect(deadlineInput).toBeDisabled()
    expect(screen.getByLabelText(/APROBANT wiersz 2/i)).toHaveValue('Lewandowska')
  })

  it('admin widzi nieaktywnego pracownika w domyślnym przypisaniu i może zatwierdzić kopię z podsumowaniem', async () => {
    const user = userEvent.setup()
    window.localStorage.setItem('access_token', 'admin-jwt')

    const copyDetail = {
      id: 11,
      source_type: 'upload',
      label: 'Stan Sprawy.xlsx',
      row_count: 1,
      error_count: 0,
      conflict_count: 0,
      created_at: '2026-11-24T10:00:00Z',
      expires_at: '2026-11-25T10:00:00Z',
      rows: [
        {
          row_index: 2,
          case_id: null,
          version: null,
          case_number: '51139292',
          title: 'ERN – Jan Kowalski',
          client_name: 'Jan Kowalski',
          assigned_to_email: 'old@example.com',
          deadline: '2027-02-01',
          date_filed: '2026-05-14',
          status: 'open',
          note: null,
          extra_columns: {},
          errors: [],
          warnings: [],
          conflict: false,
          resolution: null,
        },
      ],
    }

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
          JSON.stringify([
            { id: 1, email: 'admin@example.com', role: 'admin', is_active: true },
            { id: 4, email: 'old@example.com', role: 'user', is_active: false },
          ]),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (url.endsWith('/api/import/copies') && (!init?.method || init.method === 'GET')) {
        return new Response(JSON.stringify([copyDetail]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.endsWith('/api/import/copies/11') && (!init?.method || init.method === 'GET')) {
        return new Response(JSON.stringify(copyDetail), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.endsWith('/api/import/copies/11/commit') && init?.method === 'POST') {
        return new Response(
          JSON.stringify({ created: 1, updated: 0, skipped: 0, conflicts: [], errors: [] }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      return new Response(null, { status: 404 })
    })

    window.history.pushState({}, '', '/import')
    render(<App />)

    expect(await screen.findByText('old@example.com (nieaktywny)')).toBeInTheDocument()
    await user.click(screen.getByText('Stan Sprawy.xlsx'))

    const commitBtn = await screen.findByRole('button', { name: /Zatwierdź zmiany/i })
    await user.click(commitBtn)

    const confirmModal = await screen.findByRole('alertdialog')
    await user.click(within(confirmModal).getByRole('button', { name: /Potwierdź i zapisz/i }))

    expect(await screen.findByText(/Podsumowanie zatwierdzenia/i)).toBeInTheDocument()
    expect(screen.getByText(/utworzono 1/i)).toBeInTheDocument()
  })
})
