import { expect, test, type Page } from '@playwright/test'

async function dismissNotifPopupIfOpen(page: Page) {
  const hidePopupBtn = page.getByRole('button', { name: 'Ukryj na teraz' })
  try {
    await hidePopupBtn.waitFor({ state: 'visible', timeout: 1500 })
    await hidePopupBtn.click()
  } catch {
    // No urgent notifications popup
  }
}

async function loginAs(page: Page, email: string, password = 'Secret123!') {
  await page.goto('/login')
  await page.getByLabel(/email/i).fill(email)
  await page.getByLabel(/hasło|password/i).fill(password)
  await page.getByRole('button', { name: /zaloguj/i }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByText(`Witaj, ${email}!`)).toBeVisible()
  await dismissNotifPopupIfOpen(page)
}

test.describe('Malinois Full-Stack E2E Workflows', () => {
  test('Admin: Dashboard -> /cases filtry -> Nowa sprawa -> Edytor + Notatka -> Archiwum -> Przywróć', async ({
    page,
  }) => {
    await loginAs(page, 'admin@example.com')

    // Spec 014: Dashboard stat cards & team workload
    await expect(page.getByText('Otwarte sprawy')).toBeVisible()
    await expect(page.getByText('Obciążenie pracowników')).toBeVisible()

    // Click stat card -> /cases?status=open
    await page.getByText('Otwarte sprawy').click()
    await expect(page).toHaveURL(/\/cases\?status=open/)
    await dismissNotifPopupIfOpen(page)
    await expect(page.getByRole('button', { name: 'Wyczyść filtry' })).toBeVisible()
    await page.getByRole('button', { name: 'Wyczyść filtry' }).click()

    // Create a unique case via modal
    const tag = `E2E-${Date.now()}`
    await page.getByRole('button', { name: 'Nowa sprawa', exact: true }).click()
    await page.getByLabel('Tytuł sprawy', { exact: true }).fill(`Sprawa ${tag}`)
    await page.getByLabel('Klient', { exact: true }).fill(`Klient ${tag}`)
    await page.getByRole('button', { name: 'Utwórz sprawę' }).click()

    // Filter by q to locate our new case cleanly (wait for 300ms debounce chip)
    await page.getByLabel(/Szukaj/i).fill(tag)
    await expect(page.getByText(`Szukaj: "${tag}"`)).toBeVisible()
    const caseCell = page.getByRole('cell', { name: `Sprawa ${tag}`, exact: true })
    await expect(caseCell).toBeVisible()

    // Open inline Edytor wstępny & add a note
    await caseCell.click()
    await expect(page.getByRole('heading', { name: 'Edytor wstępny' })).toBeVisible()
    await page.getByLabel(/Treść notatki/i).fill(`Notatka ${tag}`)
    await page.getByRole('button', { name: 'Dodaj notatkę' }).click()
    await expect(page.getByText(`Notatka ${tag}`)).toBeVisible()

    // Bulk select & archive
    await page.getByLabel(`Zaznacz sprawę Sprawa ${tag}`).check()
    await expect(page.getByText('Zaznaczono: 1 spraw')).toBeVisible()
    await page.getByRole('region', { name: 'Akcje zbiorcze' }).getByRole('button', { name: 'Archiwizuj' }).click()
    await page.getByRole('button', { name: 'Zatwierdź' }).click()
    await expect(page.getByText('Zaktualizowano 1 spraw')).toBeVisible()

    // Navigate to /archive & restore
    await page.getByRole('link', { name: 'Archiwum' }).click()
    await expect(page).toHaveURL(/\/archive/)
    await dismissNotifPopupIfOpen(page)
    const row = page.locator('tr', { hasText: `Sprawa ${tag}` })
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: 'Przywróć' }).click()
    await expect(page.getByText(new RegExp(`Przywrócono sprawę.*${tag}`))).toBeVisible()
  })

  test('Admin: /settings dostępność + /admin 4 zakładki i ręczna kopia zapasowa', async ({
    page,
  }) => {
    await loginAs(page, 'admin@example.com')

    // Spec 008: Settings & accessibility tokens (auto-saves on change)
    await page.getByRole('link', { name: 'Ustawienia' }).click()
    await expect(page).toHaveURL(/\/settings/)
    await dismissNotifPopupIfOpen(page)
    await page.getByLabel(/Rozmiar czcionki/i).selectOption('large')
    await expect(page.locator('html')).toHaveAttribute('data-font-size', 'large')
    // Reset back to normal
    await page.getByLabel(/Rozmiar czcionki/i).selectOption('normal')
    await expect(page.locator('html')).toHaveAttribute('data-font-size', 'normal')

    // Spec 012 + 017: Admin Panel & Backups tab
    await page.getByRole('link', { name: 'Panel administratora' }).click()
    await expect(page).toHaveURL(/\/admin/)
    await dismissNotifPopupIfOpen(page)
    await expect(page.getByRole('tab', { name: 'Użytkownicy' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Ustawienia systemowe' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Dziennik audytu' })).toBeVisible()
    await page.getByRole('tab', { name: 'Kopie zapasowe' }).click()

    await page.getByRole('button', { name: 'Utwórz kopię zapasową' }).click()
    await expect(page.getByText(/Utworzono kopię zapasową:/i)).toBeVisible()
  })

  test('RBAC E2E: zwykły użytkownik nie ma dostępu do /admin (przekierowanie na /)', async ({
    page,
  }) => {
    await loginAs(page, 'trainee@example.com')
    await page.goto('/admin')
    await expect(page).toHaveURL(/\/$/)
  })
})
