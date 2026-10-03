import { expect, test, type Page } from '@playwright/test'

// Fixture news (e2e/fixtures/static): 2026-01-02 has a Haiti story (social, 2 sources, fact-check, outlet
// comparison) and a chip story (tech); 2026-01-01 has an earlier Haiti story.
const HAITI = 'UN extends Haiti security mission'
const CHIP = 'Chipmaker unveils faster processor'
const EARLIER = 'UN Security Council debates Haiti mission'

async function noSidewaysScroll(page: Page) {
  const { scroll, client } = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }))
  expect(scroll, 'page should not scroll sideways').toBeLessThanOrEqual(client)
}

test('front page lists the latest edition, filters by category and searches', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: "Today's news" })).toBeVisible()
  await expect(page.getByRole('link', { name: HAITI })).toBeVisible()
  await expect(page.getByRole('link', { name: CHIP })).toBeVisible()
  await expect(page.getByText('Fact-checked').first()).toBeVisible()
  await expect(page.getByText('2 outlets compared')).toBeVisible()

  await page.getByRole('button', { name: 'Technology', exact: true }).click()
  await expect(page.getByRole('link', { name: CHIP })).toBeVisible()
  await expect(page.getByRole('link', { name: HAITI })).toHaveCount(0)

  await page.getByRole('button', { name: 'All', exact: true }).click()
  await page.getByPlaceholder('Search stories and publishers').fill('processor')
  await expect(page.getByRole('link', { name: CHIP })).toBeVisible()
  await expect(page.getByRole('link', { name: HAITI })).toHaveCount(0)
})

test('article shows citations, the fact-check, outlet comparison and earlier coverage', async ({ page }) => {
  await page.goto('/article/2026-01-02/group_1')
  await expect(page.getByRole('heading', { level: 1, name: HAITI })).toBeVisible()
  await expect(page.locator('sup a').first()).toHaveAttribute('href', 'https://example.com/haiti-1')

  await expect(page.getByText(/1 statement of 5/)).toBeVisible()
  await page.getByText('See what was removed').click()
  await expect(page.getByText('The vote was unanimous.')).toBeVisible()

  await expect(page.getByRole('heading', { name: 'How each outlet covered it' })).toBeVisible()
  await expect(page.getByText('Leads with gang violence.')).toBeVisible()

  await expect(page.getByRole('heading', { name: /Earlier coverage/ })).toBeVisible()
  await page.getByRole('link', { name: EARLIER }).click()
  await expect(page).toHaveURL(/\/article\/2026-01-01\/group_1$/)
  await expect(page.getByRole('heading', { level: 1, name: EARLIER })).toBeVisible()
})

test('saving a story and following a category', async ({ page }) => {
  await page.goto('/article/2026-01-02/group_1')
  await page.getByRole('button', { name: 'Save for later' }).first().click()
  await expect(page.getByRole('link', { name: 'Saved (1)' }).first()).toBeVisible()
  await page.getByRole('link', { name: 'Saved (1)' }).first().click()
  await expect(page.getByRole('link', { name: HAITI })).toBeVisible()

  await page.goto('/')
  const tech = page.getByRole('heading', { name: /^Technology/ })
  await tech.getByRole('button', { name: 'Follow' }).click()
  await expect(tech.getByRole('button', { name: 'Following' })).toBeVisible()
  // The tech story is the only non-lead tech story, so it appears under "For you"
  await expect(page.getByRole('heading', { name: /For you/ })).toBeVisible()
})

test('archive search finds stories across editions', async ({ page }) => {
  await page.goto('/search?q=haiti')
  await expect(page.getByText('2 stories mentioning “haiti”')).toBeVisible()
  await expect(page.getByRole('link', { name: HAITI })).toBeVisible()
  await expect(page.getByRole('link', { name: EARLIER })).toBeVisible()
})

test('a reader can report a problem', async ({ page }) => {
  await page.goto('/article/2026-01-02/group_2')
  await page.getByRole('button', { name: 'Report a problem' }).click()
  const dialog = page.getByRole('dialog', { name: 'Report a problem' })
  await dialog.getByLabel('A fact is wrong').check()
  await dialog.getByLabel('Details').fill('It is three times as fast, not twice.')
  await dialog.getByRole('button', { name: 'Send report' }).click()
  await expect(dialog.getByText('Thanks, your report was sent.')).toBeVisible()
})

test('trends show the fact-check results', async ({ page }) => {
  await page.goto('/trends')
  await expect(page.getByRole('heading', { name: 'Fact-check results' })).toBeVisible()
  // 2026-01-02: 1 of 10 statements removed
  await expect(page.getByText('10%', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('writer-model', { exact: true })).toBeVisible()
})

test('chat explains when no AI provider is configured', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Ask AI' }).click()
  await page.getByLabel('Your question').fill('What happened in Haiti?')
  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByText(/No AI provider is configured/)).toBeVisible()
})

test('pages fit phone and tablet widths', async ({ page }) => {
  for (const width of [375, 820]) {
    await page.setViewportSize({ width, height: 900 })
    for (const path of ['/', '/article/2026-01-02/group_1', '/trends']) {
      await page.goto(path)
      await page.waitForLoadState('networkidle')
      await noSidewaysScroll(page)
    }
  }
})

test('unknown pages show a friendly not-found page', async ({ page }) => {
  await page.goto('/no-such-page')
  await expect(page.getByText('Page not found')).toBeVisible()
  await page.goto('/article/2026-01-02/group_99')
  await expect(page.getByText('Article not found')).toBeVisible()
})
