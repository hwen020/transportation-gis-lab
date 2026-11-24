import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'

test('390px dashboard, QA, linked selection, isolated edit, downloads and reset', async ({ page, request }) => {
  test.setTimeout(process.env.LAB_BASE_URL ? 180_000 : 45_000)
  await expect.poll(async () => {
    try {
      const health = await request.get('/healthz', { timeout: 10_000 })
      return health.ok() && (await health.json()).status === 'ok'
    } catch {
      return false
    }
  }, { timeout: process.env.LAB_BASE_URL ? 120_000 : 10_000, intervals: [1000, 2000, 5000] }).toBe(true)
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Transportation GIS & Roadway Analytics Lab')
  await expect(page.getByRole('button', { name: /^Map segment/ })).toHaveCount(8)
  await expect(page.getByRole('button', { name: /^Table segment/ })).toHaveCount(8)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await page.getByRole('button', { name: 'Quality', exact: true }).click()
  await expect(page.getByText('LRS_OVERLAP', { exact: true })).toBeVisible()
  await expect(page.getByText('MISSING_ATTRIBUTE', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Map segment SEG-007' }).press('Enter')
  await expect(page.getByRole('button', { name: 'Table segment SEG-007' })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: 'Table segment SEG-006' }).click()
  await expect(page.getByRole('button', { name: 'Map segment SEG-006' })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: 'Table segment SEG-007' }).click()
  await page.getByRole('combobox', { name: 'Surface', exact: true }).selectOption('Gravel')
  await page.getByLabel('Lanes', { exact: true }).fill('3')
  await page.getByRole('button', { name: 'Save inventory attributes' }).click()
  await expect(page.getByRole('status')).toContainText('QA and reporting recalculated')
  await expect(page.getByText('100%', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Quality', exact: true }).click()
  await expect(page.getByText('MISSING_ATTRIBUTE', { exact: true })).toHaveCount(0)
  await page.getByRole('combobox', { name: 'Route filter' }).selectOption('LAB-87')
  await expect(page.getByRole('button', { name: /^Map segment/ })).toHaveCount(2)
  await page.getByRole('button', { name: 'Reporting', exact: true }).click()
  const [jsonDownload] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Filtered GeoJSON' }).click(),
  ])
  const collection = JSON.parse(await readFile((await jsonDownload.path())!, 'utf8'))
  expect(collection.type).toBe('FeatureCollection')
  expect(collection.features).toHaveLength(2)
  expect(collection.features.find((item: { id: string }) => item.id === 'SEG-007').properties.surface).toBe('Gravel')
  const [csvDownload] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Filtered CSV' }).click(),
  ])
  const csv = await readFile((await csvDownload.path())!, 'utf8')
  expect(csv).toContain('Gravel')
  expect(csv).not.toContain('SEG-001')
  await page.getByLabel('Milepoint', { exact: true }).fill('1')
  await page.getByRole('button', { name: 'Calculate' }).click()
  await expect(page.getByText(/1\.0000 mi/)).toBeVisible()
  await page.getByRole('button', { name: 'Reset', exact: true }).click()
  await expect(page.getByRole('button', { name: /^Map segment/ })).toHaveCount(8)
  await page.getByRole('button', { name: 'Quality', exact: true }).click()
  await expect(page.getByText('MISSING_ATTRIBUTE', { exact: true })).toBeVisible()
  await page.getByRole('combobox', { name: 'Fixture' }).selectOption('clean')
  await expect(page.getByText('No findings in this view.')).toBeVisible()
  await page.getByRole('link', { name: 'Original prototype' }).click()
  await expect(page.getByRole('button', { name: 'Reset synthetic data' })).toBeVisible()
})
