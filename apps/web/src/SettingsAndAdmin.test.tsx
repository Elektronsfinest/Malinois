import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

describe('Specs 007 / 008 / 012 — Settings, Accessibility & Admin Panel', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.sessionStorage.clear()
    document.documentElement.dataset.theme = 'dark'
    document.documentElement.dataset.fontSize = 'normal'
    delete document.documentElement.dataset.highContrast
    delete document.documentElement.dataset.reducedMotion
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('przekierowuje użytkownika z must_change_password=true na /settings i odblokowuje po zmianie hasła', async () => {
    const user = userEvent.setup()
    window.localStorage.setItem('access_token', 'temp-jwt')

    let mustChange = true
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
            must_change_password: mustChange,
            ui_settings: {
              theme: 'dark',
              font_size: 'normal',
              high_contrast: null,
              reduced_motion: null,
            },
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (url.endsWith('/api/me/password') && init?.method === 'PATCH') {
        mustChange = false
        return new Response(null, { status: 204 })
      }
      return new Response(null, { status: 404 })
    })

    window.history.pushState({}, '', '/cases')
    render(<App />)

    expect(await screen.findByText(/Wymagana zmiana hasła/i)).toBeInTheDocument()

    await user.type(screen.getByLabelText(/Obecne hasło/i), 'TempPass1234!')
    await user.type(screen.getByLabelText(/^Nowe hasło$/i), 'NewStrongPass9@#')
    await user.type(screen.getByLabelText(/Potwierdź nowe hasło/i), 'NewStrongPass9@#')
    await user.click(screen.getByRole('button', { name: /Zmień hasło/i }))

    expect(await screen.findByText(/Hasło zostało zmienione/i)).toBeInTheDocument()
  })

  it('panel administratora (/admin) wyświetla 4 zakładki, zapisuje próg powiadomień i resetuje hasło z oknem jednorazowym', async () => {
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
            notification_threshold_days: 7,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (url.endsWith('/api/admin/users') && (!init?.method || init.method === 'GET')) {
        return new Response(
          JSON.stringify([
            {
              id: 1,
              email: 'admin@example.com',
              is_active: true,
              role: 'admin',
              supervisor_id: null,
              must_change_password: false,
            },
            {
              id: 3,
              email: 'trainee@example.com',
              is_active: true,
              role: 'user',
              supervisor_id: null,
              must_change_password: false,
            },
          ]),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (url.endsWith('/api/admin/users/3/reset-password') && init?.method === 'POST') {
        return new Response(JSON.stringify({ temporary_password: 'TempResetPass99!' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.endsWith('/api/admin/settings') && (!init?.method || init.method === 'GET')) {
        return new Response(JSON.stringify({ notification_threshold_days: 7 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.endsWith('/api/admin/settings') && init?.method === 'PATCH') {
        return new Response(JSON.stringify({ notification_threshold_days: 14 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      return new Response(null, { status: 404 })
    })

    window.history.pushState({}, '', '/admin')
    render(<App />)

    expect(await screen.findByRole('tab', { name: /Użytkownicy/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Ustawienia systemowe/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Dziennik audytu/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Kopie zapasowe/i })).toBeInTheDocument()

    // Open edit modal for trainee@example.com and trigger Reset hasła
    const editButtons = await screen.findAllByRole('button', { name: /^Edytuj$/i })
    await user.click(editButtons[1])
    const editModal = await screen.findByRole('dialog')
    await user.click(within(editModal).getByRole('button', { name: /Reset hasła/i }))

    const revealDialog = await screen.findByRole('alertdialog')
    expect(within(revealDialog).getByText('TempResetPass99!')).toBeInTheDocument()
    await user.click(within(revealDialog).getByRole('button', { name: /Zamknij/i }))
    await user.click(within(editModal).getByRole('button', { name: /Anuluj/i }))

    // Switch to Settings tab and update threshold to 14
    await user.click(screen.getByRole('tab', { name: /Ustawienia systemowe/i }))
    const input = await screen.findByLabelText(/Próg powiadomień/i)
    await user.clear(input)
    await user.type(input, '14')
    await user.click(screen.getByRole('button', { name: /Zapisz ustawienia/i }))
    expect(await screen.findByText(/Zapisano próg powiadomień: 14 dni/i)).toBeInTheDocument()
  })
})
