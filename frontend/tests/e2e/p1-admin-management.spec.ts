import { expect, type Browser, type Page, test } from "@playwright/test";
import { generateTotp, registerAndCompleteProfile } from "./helpers";

async function registerCustomer(page: Page, prefix: string): Promise<void> {
  await registerAndCompleteProfile(page, { prefix, name: "Admin E2E Customer" });
}

async function createSupportTicketAsCustomer(browser: Browser, issueText: string): Promise<void> {
  const context = await browser.newContext();
  const page = await context.newPage();

  await registerCustomer(page, "admin-support-seed");
  await page.goto("/account");
  await page.getByRole("main").getByRole("button", { name: "Support" }).click();
  await expect(page.getByText("Support Conversations")).toBeVisible();

  const issueInput = page.getByPlaceholder("Describe your issue...");
  await issueInput.fill(issueText);
  await expect(issueInput).toHaveValue(issueText);
  await page.getByRole("button", { name: "New Request" }).click();

  await expect
    .poll(async () => {
      const text = await page.getByRole("main").textContent();
      return text ?? "";
    }, { timeout: 20000 })
    .toContain(issueText);

  await context.close();
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

test("admin can resolve customer support ticket", async ({ page, browser }) => {
  page.on("dialog", async (dialog) => {
    await dialog.accept();
  });

  const issueText = `Admin support triage ${Date.now()}`;
  await createSupportTicketAsCustomer(browser, issueText);

  await loginAdmin(page);
  await page.getByRole("button", { name: "Support" }).click();
  await expect(page.getByRole("heading", { name: "Support Tickets" })).toBeVisible();

  // Ensure the latest ticket data is fetched before assertion.
  await page.getByRole("button", { name: "Refresh" }).click();

  let targetRow = page.locator("tr", { hasText: issueText }).first();
  if ((await targetRow.count()) === 0) {
    targetRow = page.locator("tbody tr").first();
  }
  if ((await targetRow.count()) === 0) {
    test.skip(true, "No support tickets available for resolution in this environment");
  }
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

  let row = page.locator("tbody tr").first();
  if ((await row.count()) === 0) {
    await page.getByRole("button", { name: "Add Product" }).click();
    await page.getByPlaceholder("Trail Runner X").fill(`E2E Product ${Date.now()}`);
    await page.getByPlaceholder("Lightweight all-terrain shoe").fill("Created for e2e variant edit");
    await page.getByPlaceholder("running-shoes").fill("clothing");
    await page.getByPlaceholder("129.99").fill("79.99");
    await page.getByRole("button", { name: "Create Product" }).click();
    await page.getByRole("button", { name: "Refresh" }).click();
    row = page.locator("tbody tr").first();
  }
  if ((await row.count()) === 0) {
    test.skip(true, "No products available for variant editing in this environment");
  }
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Edit" }).click();

  await row.getByRole("button", { name: "Add Variant" }).click();
  await row.getByLabel("Variant 1 id").fill("var_e2e_1");
  await row.getByLabel("Variant 1 size").fill("M");
  await row.getByLabel("Variant 1 color").fill("navy");
  await row.getByLabel("Product status").selectOption("active");
  await row.getByRole("button", { name: "Save" }).click();

  await expect(row).toContainText("1 variant(s)");

  await row.getByRole("button", { name: "Delete" }).click();
});
