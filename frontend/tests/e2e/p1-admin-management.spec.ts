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
  await expect(page.getByText("Support Tickets")).toBeVisible();

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
