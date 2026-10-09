import { test, expect } from '@playwright/test';

test.describe('Live FHIRGraph portfolio demo', () => {
  test.skip(!process.env.LIVE_DEMO, 'Requires a populated live Docker stack; run with LIVE_DEMO=1 PLAYWRIGHT_PORT=4010.');
  test('patient, graph, audit, and exact clinical evidence flow', async ({ page, request }) => {
    await page.setViewportSize({ width: 1440, height: 1400 });
    const api = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8010/api/v1';
    const summary = await request.get(`${api}/dashboard/summary`);
    expect(summary.ok()).toBeTruthy();
    expect((await summary.json()).patients).toBeGreaterThan(0);
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Knowledge Graph Dashboard' })).toBeVisible();
    await page.getByRole('link', { name: 'Patients', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Patient Registry' })).toBeVisible();
    await page.locator('a[href^="/patients/"]').first().click();
    await expect(page.getByRole('link', { name: 'Back to Registry' })).toBeVisible();
    await page.getByRole('tab', { name: 'FHIR', exact: true }).click();
    await expect(page.getByRole('tabpanel', { name: 'FHIR', exact: true })).toContainText('"resourceType": "Patient"');
    await expect(page.getByRole('tabpanel', { name: 'FHIR', exact: true })).toContainText('"birthDate"');
    await page.getByRole('link', { name: 'Graph Explorer', exact: true }).click();
    await expect(page.locator('.react-flow')).toBeVisible();
    await page.getByRole('link', { name: 'Data Quality', exact: true }).click();
    await expect(page.getByText('success', { exact: true })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'reference_resolution', exact: true })).toBeVisible();
    await page.getByRole('link', { name: 'AI Assistant', exact: true }).click();
    await page.getByRole('button', { name: 'Find patients whose latest HbA1c is above 8% with active Metformin', exact: true }).click();
    await page.getByRole('button', { name: 'Ask question', exact: true }).click();
    await expect(page.getByRole('table', { name: 'Retrieved results' })).toBeVisible();
    const observation = page.getByRole('article', { name: /^Evidence Observation\// }).first();
    await expect(observation.getByText('Observation.valueQuantity.value', { exact: true })).toBeVisible();
    await observation.getByRole('button', { name: 'Inspect FHIR source' }).click();
    await expect(observation.getByRole('region')).toContainText('"resourceType": "Observation"');
    await page.locator('main').evaluate(element => { element.scrollTop = 0; });
    await page.screenshot({ path: process.env.DEMO_SCREENSHOT || '/tmp/fhirgraph-portfolio-demo.png', fullPage: true });
    await page.getByRole('button', { name: 'Show history for Patient/p-000001', exact: true }).click();
    await page.getByRole('button', { name: 'Ask question', exact: true }).click();
    await expect(page.getByRole('columnheader', { name: 'Recorded time', exact: true })).toBeVisible();
    const encounter = page.getByRole('article', { name: /^Evidence Encounter\// }).first();
    await expect(encounter.getByText('Encounter.period.start', { exact: true })).toBeVisible();
    await encounter.getByRole('button', { name: 'Inspect FHIR source' }).click();
    await expect(encounter.getByRole('region')).toContainText('"resourceType": "Encounter"');
    for (const count of [40, 60, 80]) {
      await page.getByRole('button', { name: 'Load more results', exact: true }).click();
      await expect(page.getByText(`${count} results returned`, { exact: true })).toBeVisible();
    }
    await expect(page.getByRole('table', { name: 'Retrieved results' }).getByRole('row')).toHaveCount(81);
    await expect(page.getByRole('article', { name: 'Evidence Patient/p-000001', exact: true })).toHaveCount(1);
    await expect(page.getByText('All matching rows have been loaded.', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Load more results', exact: true })).toHaveCount(0);
    await page.getByRole('textbox', { name: 'Question' }).fill('What treatment should these patients take?');
    await page.getByRole('button', { name: 'Ask question', exact: true }).click();
    await expect(page.getByText('Unsupported question', { exact: true })).toBeVisible();
    await expect(page.getByRole('table', { name: 'Retrieved results' })).toHaveCount(0);
  });
});
