import { expect, test } from '@playwright/test';

test('drills from target ownership into class relationships and source evidence', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Project').selectOption({ label: 'Semantic fixture' });
  await expect(page.getByText('2', { exact: true }).first()).toBeVisible();
  await page.getByRole('textbox', { name: 'Search targets' }).fill('AppCore');
  await page.getByRole('button', { name: /AppCore CMAKE_TARGET/ }).click();
  await expect(page.getByRole('heading', { name: 'Classes owned by target' })).toBeVisible();
  await page.getByRole('button', { name: /Runner Explore/ }).click();
  await expect(page.getByLabel('Explore')).toHaveValue('symbol');
  await expect(page.getByRole('button', { name: /ASSOCIATION Runner → Base/ })).toBeVisible();
  await page.getByRole('button', { name: /ASSOCIATION Runner → Base/ }).click();
  await expect(page.getByRole('button', { name: /app\/runner\.hpp:9/ })).toBeVisible();
  await page.getByRole('button', { name: /app\/runner\.hpp:9/ }).click();
  await expect(page.getByText('domain::Base &service_;')).toBeVisible();
});

test('shows namespace dependencies as derived with supporting evidence', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Project').selectOption({ label: 'Semantic fixture' });
  await page.getByLabel('Explore').selectOption('namespace');
  await expect(page.getByRole('button', { name: /DERIVED app → domain/ })).toBeVisible();
  await page.getByRole('button', { name: /DERIVED app → domain/ }).click();
  await expect(page.getByText(/Derived from app::Runner USES_TYPE domain::Base/)).toBeVisible();
});
