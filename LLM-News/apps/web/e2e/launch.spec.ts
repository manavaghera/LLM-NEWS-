import { expect, test } from '@playwright/test'

test('mobile layout stays within the viewport and supports reduced motion', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.emulateMedia({ reducedMotion: 'reduce', colorScheme: 'dark' })
  await page.goto('/ai-models')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(1)
})

test('keyboard users can skip navigation and reach main content', async ({ page }) => {
  await page.goto('/')
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.locator('#main')).toBeFocused()
})

test('launch policy pages are reachable from the footer', async ({ page }) => {
  await page.goto('/privacy')
  for (const link of ['Terms', 'Cookies', 'Sources & copyright', 'Corrections']) {
    await expect(page.getByRole('link', { name: link })).toBeVisible()
  }
})
