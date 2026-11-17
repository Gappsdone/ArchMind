import { expect, test } from '@playwright/test';

test('explores a target relationship and opens verified source evidence', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Dependency explorer' })).toBeVisible();
  await expect(page.getByText('4', { exact: true }).first()).toBeVisible();
  await page.screenshot({ path: 'test-results/explorer.png', fullPage: true });
  const relationship = page.getByRole('button', { name: /BUILD Application → Simulation/ }).first();
  await relationship.click();
  await expect(page.getByText('Selected relationship')).toBeVisible();
  await expect(page.getByText('CMake codemodel target dependency; link semantics not implied')).toBeVisible();
  await page.getByRole('button', { name: /app\/CMakeLists\.txt:2/ }).click();
  await expect(page.getByText('target_link_libraries(Application PRIVATE Simulation)')).toBeVisible();
  await page.getByRole('checkbox', { name: /Build dependencies/ }).uncheck();
  await expect(page.getByRole('button', { name: /BUILD Application → Simulation/ })).toHaveCount(0);
  await page.getByRole('textbox', { name: 'Search targets' }).fill('Simulation');
  await expect(page.getByRole('button', { name: /Simulation CMAKE_TARGET/ })).toBeVisible();
});
