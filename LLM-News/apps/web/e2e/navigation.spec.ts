import { expect, test } from '@playwright/test'

const LATEST = '2026-01-02'
const ARCHIVE = '2026-01-01'
const HEADLINE = 'UN extends Haiti security mission'
const EARLIER = 'UN Security Council debates Haiti mission'
const CHAT = '**/api/chat/stream'

function deferred() {
  let resolve!: () => void
  const promise = new Promise<void>((done) => { resolve = done })
  return { promise, resolve }
}

function silence() {
  const data = Buffer.alloc(16044)
  data.write('RIFF')
  data.writeUInt32LE(data.length - 8, 4)
  data.write('WAVEfmt ', 8)
  data.writeUInt32LE(16, 16)
  data.writeUInt16LE(1, 20)
  data.writeUInt16LE(1, 22)
  data.writeUInt32LE(8000, 24)
  data.writeUInt32LE(16000, 28)
  data.writeUInt16LE(2, 32)
  data.writeUInt16LE(16, 34)
  data.write('data', 36)
  data.writeUInt32LE(16000, 40)
  return data
}

test('cached article navigation recovers from missing image and audio', async ({ page }) => {
  await page.route('**/static/**', (route) => {
    if (route.request().url().includes(ARCHIVE)) return route.fulfill({ status: 404, body: 'Missing' })
    if (route.request().url().includes('/audio/')) return route.fulfill({ contentType: 'audio/wav', body: silence() })
    return route.fulfill({
      contentType: 'image/png',
      body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6Yj4AAAAASUVORK5CYII=', 'base64'),
    })
  })
  await page.goto(`/article/${LATEST}/group_1`)
  await expect(page.locator('figure img')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Listen', exact: true })).toBeEnabled()
  await page.getByRole('link', { name: EARLIER }).click()
  await expect(page.getByRole('heading', { level: 1, name: EARLIER })).toBeVisible()
  await expect(page.locator('figure img')).toHaveCount(0)
  await expect(page.locator('audio')).toHaveCount(0)
  await page.goBack()
  await expect(page.getByRole('heading', { level: 1, name: HEADLINE })).toBeVisible()
  await expect(page.locator('figure img')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Listen', exact: true })).toBeEnabled()
})

test('archive article keeps its edition in navigation and general chat', async ({ page }) => {
  await page.route(CHAT, (route) => route.fulfill({ contentType: 'text/event-stream', body: 'data: {"type":"done"}\n\n' }))
  await page.goto(`/article/${ARCHIVE}/group_1`)
  await expect(page.getByRole('combobox', { name: 'Edition' })).toHaveValue(ARCHIVE)
  await expect(page.getByRole('link', { name: 'Daily Digest', exact: true }).first()).toHaveAttribute('href', `/digest?date=${ARCHIVE}`)
  await page.getByRole('button', { name: 'Ask about this story', exact: true }).click()
  await page.getByRole('button', { name: 'Ask generally', exact: true }).click()
  await page.getByLabel('Your question').fill('What happened that day?')
  const request = page.waitForRequest((r) => r.url().endsWith('/api/chat/stream'))
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  expect((await request).postDataJSON().context).toEqual({ currentDate: ARCHIVE })
})

test('stopping one chat scope works after another reply finishes', async ({ page }) => {
  const articleReply = deferred()
  const generalReply = deferred()
  await page.route(CHAT, async (route) => {
    const isArticle = !!route.request().postDataJSON().context?.currentGroupId
    await (isArticle ? articleReply : generalReply).promise
    await route.fulfill({
      contentType: 'text/event-stream',
      body: `data: {"type":"delta","text":"${isArticle ? 'Article answer' : 'General answer'}"}\n\ndata: {"type":"done"}\n\n`,
    }).catch(() => {}) // The general request is deliberately aborted by the reader.
  })
  try {
    await page.goto(`/article/${LATEST}/group_1`)
    await page.getByRole('button', { name: 'Ask about this story', exact: true }).click()
    await page.getByLabel('Your question').fill('Explain this article')
    const first = page.waitForRequest((r) => r.url().endsWith('/api/chat/stream'))
    await page.getByRole('button', { name: 'Send', exact: true }).click()
    await first
    await page.getByRole('button', { name: 'Ask generally', exact: true }).click()
    await page.getByLabel('Your question').fill('Explain the edition')
    const second = page.waitForRequest((r) => r.url().endsWith('/api/chat/stream'))
    await page.getByRole('button', { name: 'Send', exact: true }).click()
    await second
    const firstFinished = page.waitForResponse((r) => r.url().endsWith('/api/chat/stream'))
    articleReply.resolve()
    await (await firstFinished).finished()
    // Switching back confirms A completed before testing whether B can still be stopped.
    await page.getByRole('button', { name: 'Ask about this story', exact: true }).click()
    await expect(page.getByText('Article answer', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Stop answering', exact: true })).toHaveCount(0)
    await page.getByRole('button', { name: 'Ask generally', exact: true }).click()
    await page.getByRole('button', { name: 'Stop answering', exact: true }).click()
    await expect(page.getByText('Stopped', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Stop answering', exact: true })).toHaveCount(0)
    generalReply.resolve()
    await expect(page.getByText('General answer', { exact: true })).toHaveCount(0)
  } finally {
    articleReply.resolve()
    generalReply.resolve()
  }
})
