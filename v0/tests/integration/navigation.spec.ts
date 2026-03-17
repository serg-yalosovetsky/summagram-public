import { test, expect } from '@playwright/test';

test.describe('Navigation', () => {
    test('should navigate between main views and perform actions', async ({ page }) => {
        // Mock backend API to avoid dependency on real service
        await page.route('**/api/chats*', async route => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify([{
                    source_id: 1,
                    title: 'Test Chat',
                    description: 'Test Description',
                    importance_score: 0.8,
                    message_count_me: 5,
                    last_analyzed_at: new Date().toISOString()
                }]),
            });
        });

        await page.route('**/api/sessions*', async route => {
            if (route.request().method() === 'POST') {
                await route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify({ id: 'new-session-id', title: 'New Session' }),
                });
            } else {
                await route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify([]),
                });
            }
        });

        await page.route('**/api/documents*', async route => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify([]),
            });
        });

        await page.route('**/etl/graph/data*', async route => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ nodes: [], edges: [] }),
            });
        });

        // Start from the index page
        await page.goto('/');

        // 1. Check if the logo is present
        await expect(page.getByText('summagram')).toBeVisible();

        // 2. Navigation to Telegram Chats (Initial View)
        await expect(page.getByText('Telegram Chats')).toBeVisible();
        await expect(page.getByText('Test Chat')).toBeVisible();

        // 3. Create New Session
        await page.click('text=New Session');
        // After clicking New Session, it should navigate to Chat view.
        // We look for parts of the ChatView or Current Session in sidebar
        await expect(page.getByText('Current Session')).toBeVisible();

        // 4. Navigate to Sessions
        await page.click('nav button:has-text("Sessions")');
        await expect(page.getByRole('heading', { name: 'AI Sessions' })).toBeVisible();

        // 5. Navigate to Datasets
        await page.click('nav button:has-text("Datasets")');
        await expect(page.getByRole('heading', { name: 'Datasets' })).toBeVisible();

        // 6. Test Reprocess All Media button
        await page.route('**/etl/reindex-media*', async route => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ job_id: 'reindex-job', status: 'queued' }),
            });
        });
        await page.click('text=Reprocess All Media');
        // Toast should appear (simplified check)

        // 7. Navigate to Network
        await page.click('nav button:has-text("Network")');
        await expect(page.getByText('Social Graph')).toBeVisible();

        // 8. Navigate to Pipelines
        await page.click('nav button:has-text("Pipelines")');
        await expect(page.getByText('Pipeline Configuration')).toBeVisible();
    });
});
