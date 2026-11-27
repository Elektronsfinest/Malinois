import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

describe('Specs 006 / 009 / 010 — Archive, Edit History & Notes', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.sessionStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('strona /archive ukrywa przycisk Przywróć dla roli user i pokazuje go dla supervisor na sprawach zespołu', async () => {
    const user = userEvent.setup()
    window.localStorage.setItem('access_token', 'sup-jwt')

    let restorePayload: Record<string, unknown> | null = null

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
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
      if (url.includes('/api/cases') && url.includes('archived=true')) {
        return new Response(
          JSON.stringify({
            items: [
              {
                id: 5,
                case_number: 'ARC-5',
                title: 'Zarchiwizowana zespołu',
                client_name: 'Jan Kowalski',
                assigned_to: 3,
                assigned_to_email: 'trainee@example.com',
                assigned_to_is_active: true,
                deadline: '2027-01-10',
                date_filed: null,
                status: 'closed',
                archived: true,
                is_readonly_archive: false,
                version: 3,
                extra_fields: null,
                created_at: '2026-11-01T08:00:00Z',
                updated_at: '2026-11-02T08:00:00Z',
              },
              {
                id: 6,
                case_number: 'ARC-6',
                title: 'Poprzednio przypisana',
                client_name: 'Anna Nowak',
                assigned_to: 9,
                assigned_to_email: 'other@example.com',
                assigned_to_is_active: true,
                deadline: null,
                date_filed: null,
                status: 'closed',
                archived: true,
                is_readonly_archive: true,
                version: 4,
                extra_fields: null,
                created_at: '2026-11-01T08:00:00Z',
                updated_at: '2026-11-02T08:00:00Z',
              },
            ],
            total: 2,
            page: 1,
            page_size: 50,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (url.endsWith('/api/cases/5/restore') && init?.method === 'POST') {
        restorePayload = JSON.parse(String(init.body)) as Record<string, unknown>
        return new Response(JSON.stringify({ id: 5, archived: false, version: 4 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      return new Response(null, { status: 404 })
    })

    window.history.pushState({}, '', '/archive')
    render(<App />)

    expect(await screen.findByText('Zarchiwizowana zespołu')).toBeInTheDocument()
    expect(screen.getByText(/Tylko odczyt/i)).toBeInTheDocument()

    // Only 1 restore button (hidden for read-only past-assignee row)
    const restoreButtons = screen.getAllByRole('button', { name: /Przywróć/i })
    expect(restoreButtons).toHaveLength(1)

    await user.click(restoreButtons[0])
    expect(restorePayload).toEqual({ version: 3 })
    expect(await screen.findByText(/Przywrócono sprawę/i)).toBeInTheDocument()
  })

  it('edytor sprawy wyświetla Notatki oraz rozwijaną Historię zmian z powodem zmiany daty', async () => {
    const user = userEvent.setup()
    window.localStorage.setItem('access_token', 'admin-jwt')

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
      if (url.endsWith('/api/cases/1/notes') && (!init?.method || init.method === 'GET')) {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.endsWith('/api/cases/1/notes') && init?.method === 'POST') {
        return new Response(
          JSON.stringify({
            id: 99,
            case_id: 1,
            subject_user_id: null,
            subject_email: null,
            content: 'Nowa notatka testowa',
            author_id: 1,
            author_email: 'admin@example.com',
            created_at: '2026-11-26T08:00:00Z',
          }),
          { status: 201, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (url.includes('/api/cases/1/history')) {
        return new Response(
          JSON.stringify([
            {
              id: 10,
              field_name: 'deadline',
              old_value: '2027-01-01',
              new_value: '2027-02-01',
              reason: 'Korekta ZUS',
              changed_by_email: 'admin@example.com',
              changed_at: '2026-11-26T07:00:00Z',
            },
          ]),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (url.includes('/api/cases')) {
        return new Response(
          JSON.stringify({
            items: [
              {
                id: 1,
                case_number: 'C-1',
                title: 'Sprawa testowa',
                client_name: 'Jan Kowalski',
                assigned_to: 3,
                assigned_to_email: 'trainee@example.com',
                assigned_to_is_active: true,
                deadline: '2027-02-01',
                date_filed: null,
                status: 'open',
                archived: false,
                version: 2,
                extra_fields: null,
                created_at: '2026-11-01T08:00:00Z',
                updated_at: '2026-11-02T08:00:00Z',
              },
            ],
            total: 1,
            page: 1,
            page_size: 50,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      return new Response(null, { status: 404 })
    })

    window.history.pushState({}, '', '/cases')
    render(<App />)

    await user.click(await screen.findByRole('button', { name: /^Edytuj$/i }))

    const editor = screen.getByLabelText('Edytor wstępny')
    const noteBox = within(editor).getByLabelText(/Treść notatki/i)
    await user.type(noteBox, 'Nowa notatka testowa')
    await user.click(within(editor).getByRole('button', { name: /Dodaj notatkę/i }))
    expect(await within(editor).findByText('Nowa notatka testowa')).toBeInTheDocument()

    await user.click(within(editor).getByRole('button', { name: /Historia zmian/i }))
    expect(await within(editor).findByText(/Powód: Korekta ZUS/i)).toBeInTheDocument()
  })
})
