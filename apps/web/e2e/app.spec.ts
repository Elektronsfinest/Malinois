import { expect, test } from '@playwright/test'

test.describe('Flow Autoryzacji E2E (TDD)', () => {
  test('niezalogowany użytkownik jest przekierowywany z / na /login', async ({
    page,
  }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByLabel(/email/i)).toBeVisible()
    await expect(page.getByLabel(/hasło|password/i)).toBeVisible()
  })

  test('błędne dane logowania wyświetlają komunikat "Niepoprawny login lub hasło"', async ({
    page,
  }) => {
    await page.goto('/login')

    await page.getByLabel(/email/i).fill('trainee@example.com')
    await page.getByLabel(/hasło|password/i).fill('ZleHaslo123!')
    await page.getByRole('button', { name: /zaloguj/i }).click()

    await expect(
      page.getByText('Niepoprawny login lub hasło')
    ).toBeVisible()
  })

  test('poprawne logowanie wyświetla powitanie na Dashboardzie, a Wyloguj czyści sesję', async ({
    page,
  }) => {
    await page.goto('/login')

    await page.getByLabel(/email/i).fill('trainee@example.com')
    await page.getByLabel(/hasło|password/i).fill('Secret123!')
    await page.getByRole('button', { name: /zaloguj/i }).click()

    await expect(
      page.getByText('Witaj, trainee@example.com!')
    ).toBeVisible()

    await page.getByRole('button', { name: /wyloguj/i }).click()

    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByLabel(/email/i)).toBeVisible()
  })
})
