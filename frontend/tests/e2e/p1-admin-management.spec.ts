import { expect, type Page, test } from "@playwright/test";
import { generateTotp, registerAndCompleteProfile } from "./helpers";

async function createSupportTicketAsCustomer(page: Page, issueText: string): Promise<void> {
  await registerAndCompleteProfile(page, { prefix: "admin-support-seed", name: "Admin Support Seed" });
  await page.goto("/account");
  await page.getByRole("main").getByRole("button", { name: "Support" }).click();
  await expect(page.getByText("Support Conversations")).toBeVisible();
  await page.getByPlaceholder("Describe your issue...").fill(issueText);
  await page.getByRole("button", { name: "New Request" }).click();
  await expect(page.locator(".premium-card", { hasText: issueText }).first()).toBeVisible();
}

async function loginAdmin(page: Page): Promise<void> {
  await page.context().clearCookies();
  await page.goto("/");
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  await page.goto("/admin/login");
  await page.getByPlaceholder("admin@example.com").fill("admin@example.com");
  await page.getByPlaceholder("••••••••••").fill("AdminPass123!");
  await page.getByRole("button", { name: "Continue" }).click();

  const otp = generateTotp("JBSWY3DPEHPK3PXP");
  for (let i = 1; i <= 6; i += 1) {
    await page.getByLabel(`One-time passcode digit ${i}`).fill(otp[i - 1]);
  }

  await page.getByRole("button", { name: "Verify & Access Dashboard" }).click();
  await expect(page).toHaveURL(/\/admin$/);
}

test("admin can resolve customer support ticket", async ({ page }) => {
  page.on("dialog", async (dialog) => {
    await dialog.accept();
  });

  const issueText = `Admin support triage ${Date.now()}`;
  await createSupportTicketAsCustomer(page, issueText);

  await loginAdmin(page);
  await page.getByRole("button", { name: "Support" }).click();
  await expect(page.getByRole("heading", { name: "Support Tickets" })).toBeVisible();

  await expect
    .poll(async () => {
      await page.getByRole("button", { name: "Refresh" }).click();
      return await page.locator("tr", { hasText: issueText }).count();
    }, { timeout: 30000 })
    .toBeGreaterThan(0);

  const targetRow = page.locator("tr", { hasText: issueText }).first();
  await expect(targetRow).toBeVisible();
  await targetRow.getByRole("button", { name: "Resolve" }).click();

  const statusCell = targetRow.locator("td").nth(3);
  await expect(statusCell).toContainText(/resolved/i);
});

test("admin can create category and edit inventory", async ({ page }) => {
  await loginAdmin(page);

  await page.getByRole("button", { name: "Categories" }).click();
  await expect(page.getByRole("heading", { name: "Categories" })).toBeVisible();

  const categoryName = `E2E Category ${Date.now()}`;
  await page.getByPlaceholder("Running Shoes").fill(categoryName);
  await page.getByPlaceholder("running-shoes").fill(`e2e-cat-${Date.now()}`);
  await page.getByPlaceholder("Category description").fill("E2E category description");
  await page.getByRole("button", { name: "Create Category" }).click();

  await page.getByRole("button", { name: "Inventory" }).click();
  await expect(page.getByText("Inventory Control")).toBeVisible();

  const productSelect = page.locator("main select").nth(0);
  const variantSelect = page.locator("main select").nth(1);
  await expect(productSelect).toBeVisible();
  await expect(variantSelect).toBeVisible();
  await expect(page.getByRole("button", { name: "Load Inventory" })).toBeVisible();
});

test("admin can edit product variants", async ({ page }) => {
  page.on("dialog", async (dialog) => {
    await dialog.accept();
  });

  await loginAdmin(page);

  await page.getByRole("button", { name: "Products" }).click();
  await expect(page.getByRole("heading", { name: /Products/i })).toBeVisible();

  await expect
    .poll(async () => {
      await page.getByRole("button", { name: "Refresh" }).click();
      return await page.locator("tbody tr").count();
    }, { timeout: 30000 })
    .toBeGreaterThan(0);

  const row = page.locator("tbody tr").first();
  await expect(row).toBeVisible();

  await row.getByRole("button", { name: "Edit" }).click();

  const existingVariantInputCount = await row.locator('input[aria-label$=" id"]').count();
  const newVariantIndex = existingVariantInputCount + 1;

  await row.getByRole("button", { name: "Add Variant" }).click();
  await expect(row.locator('input[aria-label$=" id"]')).toHaveCount(newVariantIndex);
  await row.getByLabel(`Variant ${newVariantIndex} id`).fill(`var_e2e_${Date.now()}`);
  await row.getByLabel(`Variant ${newVariantIndex} size`).fill("M");
  await row.getByLabel(`Variant ${newVariantIndex} color`).fill("navy");
  await row.getByLabel("Product status").selectOption("active");
  await row.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Product updated")).toBeVisible();
});
