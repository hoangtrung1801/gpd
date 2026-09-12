// Playwright E2E spec for GPD demo flow.
// Compatible with both Playwright and Vitest test runners.
const playwrightPkg = "@playwright/test";

const { test, expect } = await (async () => {
  try {
    return await import(/* @vite-ignore */ playwrightPkg);
  } catch {
    const v = await import("vitest");
    return { test: v.test.skip, expect: v.expect };
  }
})();

test("judge can inspect the complete project-memory loop", async ({ page }: { page: any }) => {
  // 1. Inspect bug task created from Slack thread
  await page.goto("/tasks/BUG-1");
  await expect(page.getByRole("heading", { name: /Checkout hangs on expired card/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Slack message/i })).toBeVisible();
  await expect(page.getByText("payment_method_invalid")).toBeVisible();

  // 2. Navigate to knowledge review gate
  const reviewLink = page.getByRole("link", { name: /Knowledge review|Review/i }).first();
  await reviewLink.click();

  // 3. Inspect confirmed knowledge item / proposal
  await expect(page.getByText("Normalize payment errors in PaymentService")).toBeVisible();
});
