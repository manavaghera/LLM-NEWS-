import { expect, test, type Page } from '@playwright/test'

const DATE = '2026-01-02'
const HAITI = 'UN extends Haiti security mission'
const CHIP = 'Chipmaker unveils faster processor'

async function noOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
}

test('library backups download, reject invalid files and merge without duplicates', async ({ page }, testInfo) => {
  await page.goto(`/article/${DATE}/group_1`)
  await page.getByRole('button', { name: 'Save for later' }).click()
  await page.getByRole('button', { name: 'Follow this story', exact: true }).click()
  await page.getByRole('link', { name: 'Saved (1)', exact: true }).first().click()
  const downloaded = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export library' }).click()
  const download = await downloaded
  expect(download.suggestedFilename()).toMatch(/^newssense-library-.*\.json$/)
  const stream = await download.createReadStream()
  const chunks: Buffer[] = []
  for await (const chunk of stream) chunks.push(Buffer.from(chunk))
  const exported = JSON.parse(Buffer.concat(chunks).toString('utf8'))
  expect(exported.version).toBe(1)
  expect(exported.saved[0].headline).toBe(HAITI)
  expect(exported.stories[0].headline).toBe(HAITI)

  const input = page.getByLabel('Library backup file')
  await input.setInputFiles({ name: 'bad.json', mimeType: 'application/json', buffer: Buffer.from('{bad') })
  await expect(page.getByRole('alert')).toHaveText('This file is not valid JSON.')
  const savedStories = page.locator('section[aria-labelledby^="saved-"]')
  await expect(savedStories.getByRole('link', { name: HAITI })).toBeVisible()
  exported.saved.push({ date: DATE, group_id: 'group_2', headline: CHIP, category: 'tech', saved_at: 1 })
  exported.categories = ['tech']
  exported.keywords = ['processor']
  const valid = { name: 'library.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(exported)) }
  await input.setInputFiles(valid)
  await expect(page.getByRole('status')).toContainText('Library imported')
  await input.setInputFiles(valid)
  await expect(savedStories.getByRole('link', { name: HAITI })).toHaveCount(1)
  await expect(savedStories.getByRole('link', { name: CHIP })).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Stop following Technology' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Stop following “processor”' })).toBeVisible()
  await expect(page.getByRole('button', { name: `Stop following story: ${HAITI}` })).toHaveCount(1)
  for (const width of [375, 820]) {
    await page.setViewportSize({ width, height: 900 })
    await noOverflow(page)
    if (width === 375) await page.screenshot({ path: testInfo.outputPath('saved-phone.png'), fullPage: true })
  }
})

test('followed-topic alerts poll new stories and preserve read state', async ({ page }) => {
  await page.clock.install()
  await page.addInitScript(() => localStorage.setItem('newssense-library', JSON.stringify({ saved: [], categories: ['tech'], keywords: [] })))
  const stories = [{ id: 2, date: DATE, group_id: 'group_2', headline: CHIP, summary: 'A processor', category: 'tech', content: '', image_url: '', has_image: false }]
  await page.route(`**/api/news?date=${DATE}`, (route) => route.fulfill({ json: stories }))
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Alerts, 1 unread', exact: true })).toBeVisible()
  stories.push({ ...stories[0], id: 3, group_id: 'group_3', headline: 'Another processor announced' })
  await page.clock.fastForward(61_000)
  await expect(page.getByRole('button', { name: 'Alerts, 2 unread', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Alerts, 2 unread', exact: true }).click()
  const menu = page.getByRole('region', { name: 'Story alerts' })
  await expect(menu.getByRole('link', { name: /Another processor announced/ })).toBeVisible()
  await menu.getByRole('button', { name: 'Mark all read' }).click()
  await expect(page.getByRole('button', { name: 'Alerts', exact: true })).toBeVisible()
  await page.reload()
  await page.getByRole('button', { name: 'Alerts', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Story alerts' }).getByRole('link', { name: CHIP, exact: true })).toHaveCount(1)
  await expect(page.getByRole('button', { name: /Alerts, \d+ unread/ })).toHaveCount(0)
})

test('owner dashboard authenticates, changes a budget, resolves reports and publishes corrections', async ({ page }, testInfo) => {
  const token = 'owner-test-token'
  let authenticated = false
  let report = { id: 1, date: DATE, group_id: 'group_1', created_at: `${DATE}T10:00:00Z`, kind: 'wrong_fact', message: 'The duration is incorrect.', status: 'open', resolution: '', resolved_at: null as string | null, original_headline: HAITI, article_matches: true }
  const corrections: { id: number; created_at: string; text: string }[] = []
  let usage = { date: DATE, month: '2026-01', pipeline_calls: 2, pipeline_limit: 20, remaining: 18, monthly_calls: 8, monthly_limit: 400, monthly_remaining: 392, models: [{ provider: 'Test', model: 'fixture-model', calls: 2, failed: 0, prompt_tokens: 10, completion_tokens: 5 }] }
  const operations = () => ({
    update: { date: DATE, last_update: `${DATE}T10:00:00Z`, next_update: null, interval_minutes: null, added: 2, ok: true },
    feeds: [{ publisher: 'Fixture News', url: 'https://example.com/feed', category: 'social', ok: true, items: 2, full_text_items: 1, error: null, last_checked: `${DATE}T10:00:00Z` }],
    runs: [], usage, held_stories: [{ date: DATE, category: 'tech', headline: 'Held fixture story', reason: 'A claim could not be matched to a source.', created_at: `${DATE}T10:00:00Z` }],
    analytics: { days: 30, since: DATE, privacy: 'Aggregate counters only; no visitor identifiers or query text are stored.', events: [], requests: [] },
  })
  await page.route('**/api/admin/**', async (route) => {
    if (route.request().url().endsWith('/login')) {
      if (route.request().postDataJSON().token !== token) return route.fulfill({ status: 401, json: { detail: 'Invalid admin credentials' } })
      authenticated = true
      return route.fulfill({ json: { status: 'authenticated', expires_in: 28800 } })
    }
    if (route.request().url().endsWith('/logout')) { authenticated = false; return route.fulfill({ json: { status: 'signed_out' } }) }
    return authenticated ? route.fulfill({ json: { authenticated: true } }) : route.fulfill({ status: 404, json: { detail: 'Not found' } })
  })
  await page.route('**/api/operations**', async (route) => {
    if (!authenticated) return route.fulfill({ status: 404, json: { detail: 'Not found' } })
    if (route.request().method() === 'PATCH') {
      expect(route.request().postDataJSON()).toEqual({ daily_call_limit: 12, monthly_call_limit: 400 })
      usage = { ...usage, pipeline_limit: 12, remaining: 10 }
      return route.fulfill({ json: usage })
    }
    return route.fulfill({ json: operations() })
  })
  await page.route('**/api/reports**', async (route) => {
    if (route.request().url().includes('/corrections/')) return route.fulfill({ json: { corrections } })
    if (!authenticated) return route.fulfill({ status: 404, json: { detail: 'Not found' } })
    if (route.request().method() === 'PATCH') {
      report = { ...report, ...route.request().postDataJSON(), resolved_at: `${DATE}T11:00:00Z` }
      return route.fulfill({ json: { report } })
    }
    if (route.request().method() === 'POST') {
      const note = { id: 1, created_at: `${DATE}T12:00:00Z`, text: route.request().postDataJSON().text }
      corrections.push(note)
      report = { ...report, status: 'resolved', resolution: note.text, resolved_at: note.created_at }
      return route.fulfill({ status: 201, json: { status: 'resolved', correction: note } })
    }
    return route.fulfill({ json: { reports: [report] } })
  })
  await page.goto('/admin')
  await page.getByLabel('Admin token').fill('incorrect')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Could not sign in')
  await page.getByLabel('Admin token').fill(token)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Pipeline health' })).toBeVisible()
  await expect(page.getByText('Held fixture story', { exact: true })).toBeVisible()
  await expect(page.getByText('fixture-model', { exact: false })).toBeVisible()
  for (const width of [375, 820]) {
    await page.setViewportSize({ width, height: 900 })
    await noOverflow(page)
    if (width === 375) await page.screenshot({ path: testInfo.outputPath('admin-phone.png'), fullPage: true })
  }
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.getByLabel('Daily call limit (0 removes the limit)').fill('12')
  await page.getByRole('button', { name: 'Save limits', exact: true }).click()
  await expect(page.getByText(/2 calls.*10 remaining/)).toBeVisible()
  await page.getByLabel('Private resolution note').fill('Checked the source report.')
  await page.getByRole('button', { name: 'Resolve report', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Reader reports (0 open)' })).toBeVisible()
  await page.getByLabel('Report status').selectOption('resolved')
  await page.getByText('Publish an article correction', { exact: true }).click()
  await page.getByLabel('Public correction').fill('Correction: the mission was extended for six months.')
  await page.getByRole('button', { name: 'Publish correction', exact: true }).click()
  await expect(page.getByText('Correction published and report resolved.', { exact: true })).toBeVisible()
  expect(await page.evaluate((secret) => JSON.stringify([localStorage, sessionStorage]).includes(secret), token)).toBe(false)
  await page.getByRole('link', { name: /Read article ·/ }).click()
  await expect(page.getByRole('heading', { name: 'Corrections & updates' })).toBeVisible()
  await expect(page.getByText('Correction: the mission was extended for six months.', { exact: true })).toBeVisible()
  await page.goto('/admin')
  await expect(page.getByRole('heading', { name: 'Pipeline health' })).toBeVisible()
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page.getByLabel('Admin token')).toHaveValue('')
})

test('claim evidence shows verified excerpts and allows only safe source links', async ({ page }) => {
  await page.route(`**/api/news/articles/${DATE}/group_1`, async (route) => {
    const response = await route.fetch()
    const article = await response.json()
    article.claim_check.evidence = [{ id: 'claim-1', text: 'The mission was extended for six months.', field: 'body', section_index: 0, sources: [
      { url: 'https://example.com/source', publisher: 'FixtureNews', quote: 'Members voted to extend the mandate by six months.' },
      { url: 'javascript:alert(1)', publisher: 'Unsafe source', quote: '<script>must stay plain text</script>' },
    ] }]
    await route.fulfill({ json: article })
  })
  await page.goto(`/article/${DATE}/group_1`)
  await page.getByRole('region', { name: 'Claim evidence' }).getByText('The mission was extended for six months.', { exact: true }).click()
  await expect(page.getByText('“Members voted to extend the mandate by six months.”', { exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Fixture News', exact: true })).toHaveAttribute('href', 'https://example.com/source')
  await expect(page.locator('a[href^="javascript:"]')).toHaveCount(0)
  await expect(page.getByText('“<script>must stay plain text</script>”', { exact: true })).toBeVisible()
})
