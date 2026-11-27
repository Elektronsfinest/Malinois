import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

describe('Autoryzacja i Dashboard (TDD)', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.sessionStorage.clear()
    window.history.pushState({}, '', '/')
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Protected Route i Strona Logowania (/login)', () => {
    it('przekierowuje niezalogowanego użytkownika z / do formularza logowania (/login)', async () => {
      render(<App />)

      await waitFor(() => {
        expect(
          screen.getByLabelText(/email/i, { selector: 'input' })
        ).toBeInTheDocument()
      })
      expect(
        screen.getByLabelText(/hasło|password/i, { selector: 'input' })
      ).toBeInTheDocument()
      expect(
        screen.getByRole('button', { name: /zaloguj/i })
      ).toBeInTheDocument()
    })

    it('waliduje puste pola oraz niepoprawny format adresu email przed wysłaniem zapytania', async () => {
      const user = userEvent.setup()
      const fetchSpy = vi.spyOn(globalThis, 'fetch')
      window.history.pushState({}, '', '/login')

      render(<App />)

      const submitButton = await screen.findByRole('button', {
        name: /zaloguj/i,
      })
      await user.click(submitButton)

      expect(fetchSpy).not.toHaveBeenCalled()

      const emailInput = screen.getByLabelText(/email/i, { selector: 'input' })
      const passwordInput = screen.getByLabelText(/hasło|password/i, {
        selector: 'input',
      })

      await user.type(emailInput, 'niepoprawny-email')
      await user.type(passwordInput, 'Secret123!')
      await user.click(submitButton)

      expect(fetchSpy).not.toHaveBeenCalled()
    })

    it('wyświetla komunikat "Niepoprawny login lub hasło", gdy backend zwróci błąd 401', async () => {
      const user = userEvent.setup()
      vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Invalid credentials' }), {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        })
      )
      window.history.pushState({}, '', '/login')

      render(<App />)

      const emailInput = await screen.findByLabelText(/email/i, {
        selector: 'input',
      })
      const passwordInput = screen.getByLabelText(/hasło|password/i, {
        selector: 'input',
      })
      const submitButton = screen.getByRole('button', { name: /zaloguj/i })

      await user.type(emailInput, 'trainee@example.com')
      await user.type(passwordInput, 'BledneHaslo123!')
      await user.click(submitButton)

      expect(
        await screen.findByText(/Niepoprawny login lub hasło/i)
      ).toBeInTheDocument()
    })
  })

  describe('Proces logowania, Widok Główny (/) i Wylogowanie', () => {
    it('po udanym logowaniu zapisuje token, wyświetla "Witaj, trainee@example.com!" i pozwala się wylogować', async () => {
      const user = userEvent.setup()
      vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
        const url = typeof input === 'string' ? input : input.toString()
        if (url.endsWith('/api/login')) {
          return new Response(
            JSON.stringify({
              access_token: 'fake-jwt-token-123',
              token: 'fake-jwt-token-123',
              user: { email: 'trainee@example.com' },
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          )
        }
        if (url.endsWith('/api/me')) {
          return new Response(
            JSON.stringify({ email: 'trainee@example.com', is_active: true }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          )
        }
        return new Response(null, { status: 404 })
      })

      window.history.pushState({}, '', '/login')
      render(<App />)

      const emailInput = await screen.findByLabelText(/email/i, {
        selector: 'input',
      })
      const passwordInput = screen.getByLabelText(/hasło|password/i, {
        selector: 'input',
      })
      const submitButton = screen.getByRole('button', { name: /zaloguj/i })

      await user.type(emailInput, 'trainee@example.com')
      await user.type(passwordInput, 'Secret123!')
      await user.click(submitButton)

      expect(
        await screen.findByText(/Witaj,\s*trainee@example\.com!/i)
      ).toBeInTheDocument()

      const storedToken =
        window.localStorage.getItem('token') ||
        window.localStorage.getItem('access_token') ||
        window.sessionStorage.getItem('token') ||
        window.sessionStorage.getItem('access_token')
      expect(storedToken).toBe('fake-jwt-token-123')

      const logoutButton = screen.getByRole('button', { name: /wyloguj/i })
      await user.click(logoutButton)

      await waitFor(() => {
        expect(
          screen.getByLabelText(/email/i, { selector: 'input' })
        ).toBeInTheDocument()
      })
      expect(window.localStorage.getItem('token')).toBeNull()
      expect(window.localStorage.getItem('access_token')).toBeNull()
      expect(window.sessionStorage.getItem('token')).toBeNull()
      expect(window.sessionStorage.getItem('access_token')).toBeNull()
    })
  })

  describe('RBAC — role badge i strażnik trasy /admin', () => {
    it('użytkownik admin widzi odznakę Administrator i link do Panelu administratora', async () => {
      const user = userEvent.setup()
      window.localStorage.setItem('access_token', 'admin-jwt')
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(
          JSON.stringify({
            id: 2,
            email: 'admin@example.com',
            is_active: true,
            role: 'admin',
            supervisor_id: null,
            must_change_password: false,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      )

      window.history.pushState({}, '', '/')
      render(<App />)

      expect(await screen.findByText('Administrator')).toBeInTheDocument()
      const adminLink = screen.getByRole('link', {
        name: /Panel administratora/i,
      })
      expect(adminLink).toBeInTheDocument()

      await user.click(adminLink)
      expect(
        await screen.findByRole('heading', { name: /Panel administratora/i })
      ).toBeInTheDocument()
    })

    it('użytkownik bez roli admin nie widzi linku /admin i jest przekierowywany z /admin na /', async () => {
      window.localStorage.setItem('access_token', 'supervisor-jwt')
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(
          JSON.stringify({
            id: 3,
            email: 'supervisor@example.com',
            is_active: true,
            role: 'supervisor',
            supervisor_id: null,
            must_change_password: false,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      )

      window.history.pushState({}, '', '/admin')
      render(<App />)

      expect(
        await screen.findByText(/Witaj,\s*supervisor@example\.com!/i)
      ).toBeInTheDocument()
      expect(screen.getByText('Nadrzędny')).toBeInTheDocument()
      expect(
        screen.queryByRole('link', { name: /Panel administratora/i })
      ).not.toBeInTheDocument()
    })
  })
})
