import { expect, test } from '@playwright/test';

test('keeps selected edge context across investigation follow-ups and shows proposal only', async ({ page }) => {
  const selected: Record<string, string>[] = [];
  const prompts: string[] = [];
  await page.route('**/api/v1/investigations', async route => {
    selected.push(route.request().postDataJSON());
    await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ id: 'investigation-test', turns: [] }) });
  });
  await page.route('**/api/v1/investigations/investigation-test/messages', async route => {
    prompts.push(route.request().postDataJSON().question);
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ answer: 'Review this adapter extraction.', findings: [], hypotheses: ['Header ownership may be incomplete'], uncertainty: ['Build order is not link evidence'], alternatives: [{ title: 'Extract adapter', rationale: 'Isolate GUI', impact: 'Build affected targets', tradeoffs: ['More targets'], risks: ['Link order'], affected_targets: ['Application'], affected_files: [], complexity: 'medium', plan_steps: ['Edit in a worktree', 'Run tests'] }], status: 'proposal_only' }) });
  });
  await page.goto('/');
  await page.getByRole('button', { name: /BUILD Application → Simulation/ }).first().click();
  await page.getByRole('button', { name: 'Explain origin' }).click();
  await expect(page.getByText('Review this adapter extraction.')).toBeVisible();
  await page.getByRole('button', { name: 'Explore removal' }).click();
  await expect(page.getByText('Extract adapter')).toHaveCount(2);
  expect(prompts).toHaveLength(2);
  expect(selected[0]?.relationship).toBe('BUILD_DEPENDS_ON');
  expect(selected[0]?.edge_id).toBeTruthy();
  expect(selected[0]?.snapshot_id).toBeTruthy();
  await expect(page.getByText(/proposal only/i).first()).toBeVisible();
});
