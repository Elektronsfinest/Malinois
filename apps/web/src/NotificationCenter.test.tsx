import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

describe('NotificationCenter (Spec 005)', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.sessionStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    delete (window as { Notification?: unknown }).Notification
  })

  it('wyświetla badge dzwonka, otwiera popup alertdialog, pozwala odrzucić i zamknąć sprawę oraz wywołuje Windows Notification', async () => {
    const user = userEvent.setup()
    window.localStorage.setItem('access_token', 'user-jwt')

    const desktopNotifSpy = vi.fn()
    class MockNotification {
      static permission = 'granted'
      static requestPermission = vi.fn().mockResolvedValue('granted')
      onclick: (() => void) | null = null
      close = vi.fn()
      constructor(title: string, options?: NotificationOptions) {
        desktopNotifSpy(title, options)
      }
    }
    ;(window as unknown as { Notification: typeof MockNotification }).Notification = MockNotification

    const notifications = [
      {
        case_id: 1,
        case_title: 'Pilna zaległa sprawa',
        client_name: 'Jan Kowalski',
        assigned_to_email: 'trainee@example.com',
        deadline: '2026-11-20',
        days_remaining: -6,
        urgency: 'overdue',
        version: 2,
      },
      {
        case_id: 2,
        case_title: 'Sprawa na dzisiaj',
        client_name: 'Anna Nowak',
        assigned_to_email: 'trainee@example.com',
        deadline: '2026-11-26',
        days_remaining: 0,
        urgency: 'upcoming',
        version: 1,
      },
    ]

    let dismissCalled = false
    let closePayload: Record<string, unknown> | null = null

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
      if (url.endsWith('/api/notifications') && (!init?.method || init.method === 'GET')) {
        return new Response(JSON.stringify(notifications), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.endsWith('/api/notifications/1/dismiss') && init?.method === 'POST') {
        dismissCalled = true
        return new Response(null, { status: 204 })
      }
      if (url.endsWith('/api/cases/2') && init?.method === 'PATCH') {
        closePayload = JSON.parse(String(init.body)) as Record<string, unknown>
        return new Response(JSON.stringify({ id: 2, status: 'closed', version: 2 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      return new Response(null, { status: 404 })
    })

    window.history.pushState({}, '', '/')
    render(<App />)

    const dialog = await screen.findByRole('alertdialog')
    expect(within(dialog).getByText('Pilna zaległa sprawa')).toBeInTheDocument()
    expect(within(dialog).getByText(/Termin dzisiaj/i)).toBeInTheDocument()
    expect(desktopNotifSpy).toHaveBeenCalledTimes(1)

    // Dismiss first notification
    const dismissButtons = within(dialog).getAllByRole('button', { name: /^Zamknij$/i })
    await user.click(dismissButtons[0])
    expect(dismissCalled).toBe(true)

    // Close second case directly from popup
    const closeCaseBtn = await within(dialog).findByRole('button', { name: /Zakończ sprawę/i })
    await user.click(closeCaseBtn)
    expect(closePayload).toEqual({ version: 1, status: 'closed' })
  })
})
