import { expect, test, type Page } from '@playwright/test';

const VIEWPORTS = [
  { name: 'phone', width: 390, height: 844 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1024, height: 768 },
] as const;

const TRANSPARENT_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
);

async function stubMapTiles(page: Page) {
  await page.route('https://*.tile.openstreetmap.org/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/png',
      body: TRANSPARENT_PNG,
    });
  });
}

async function stubPublicPhoto(page: Page) {
  await page.route('https://cdn.example/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/jpeg',
      body: TRANSPARENT_PNG,
    });
  });
}

async function expectPublicPhotoLoaded(page: Page) {
  const photo = page.getByRole('img', { name: 'Public photo for BG-100001' });
  await expect(photo).toBeVisible();
  await expect(photo).toHaveAttribute('src', 'https://cdn.example/redacted.jpg');
  await expect(photo).toHaveJSProperty('naturalWidth', 1);
  await expect(page.getByLabel('No public photo available')).toHaveCount(0);
  await expect(page.locator('body')).not.toContainText(
    /imageObjectKey|publicImageObjectKey|originalImageUrl|reports\/photos\/v2|private-media\.example|hidden-key/i,
  );
}

test.describe('built SPA browser subset', () => {
  test('serves notification deep links through the SPA fallback', async ({ page }) => {
    const response = await page.goto('/t/ABC234');
    expect(response?.ok()).toBeTruthy();
    await expect(page.getByTestId('notification-link-guest')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Track with this code' })).toHaveAttribute(
      'href',
      '/track?trackingCode=ABC234',
    );
    await expect(page.locator('body')).not.toContainText(/not yours|does not belong/i);
  });

  test('tracks a resolved report and keeps only the citizen-safe outcome message', async ({
    page,
  }) => {
    await page.goto('/track');
    await page.getByLabel('Tracking code').fill('RES234');
    await page.getByRole('button', { name: 'Look up' }).click();
    await expect(page.getByTestId('track-outcome')).toHaveText(
      'The reported issue has been resolved.',
    );
    await expect(page.locator('body')).not.toContainText(
      /WORK_COMPLETED|private crew address|Internal close note|secret-ticket-id/,
    );
  });

  test('loads the public redacted photo and keeps private image fields unavailable', async ({
    page,
  }) => {
    await stubPublicPhoto(page);
    await page.goto('/reports');
    await expect(page.getByTestId('public-report-list')).toBeVisible();
    await expectPublicPhotoLoaded(page);

    await page.goto('/public/BG-100001');
    await expect(page.getByTestId('public-detail')).toBeVisible();
    await expectPublicPhotoLoaded(page);
  });

  test('renders the public map from the production bundle', async ({ page }) => {
    await stubMapTiles(page);
    await page.goto('/map');
    await expect(page.getByTestId('public-map')).toBeVisible();
    await expect(page.locator('.leaflet-container')).toBeVisible();
    await expect(page.getByRole('link', { name: 'View as list' })).toHaveAttribute(
      'href',
      '/reports',
    );
  });

  test('restores a deep link after cookie OTP against the controlled API', async ({ page }) => {
    await page.goto('/login?returnTo=/t/ABC234');
    await page.getByLabel('Phone number').fill('70123456');
    await page.getByRole('button', { name: /Continue/ }).click();
    await page.getByLabel('Verification code').fill('123456');

    const verify = page.waitForResponse(
      (response) =>
        response.url().includes('/v1/citizen/auth/otp/verify') &&
        response.request().method() === 'POST',
    );
    await page.getByRole('button', { name: 'Verify and continue' }).click();
    const verifyResponse = await verify;
    expect(verifyResponse.ok()).toBe(true);
    expect(verifyResponse.url()).toContain('127.0.0.1:18080');
    expect(verifyResponse.headers()['access-control-allow-origin']).toBe('http://127.0.0.1:4174');
    expect(verifyResponse.headers()['access-control-allow-credentials']).toBe('true');

    await expect(page.getByTestId('track-result')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/Tracking code: ABC234/)).toBeVisible();
  });

  for (const viewport of VIEWPORTS) {
    test(`keeps critical chrome usable at the ${viewport.name} width`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto('/reports');
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible();
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow).toBeLessThanOrEqual(8);
    });
  }
});
