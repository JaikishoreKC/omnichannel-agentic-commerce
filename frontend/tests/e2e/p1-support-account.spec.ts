import { expect, type Page, test } from "@playwright/test";

function uniqueEmail(prefix: string): string {
  const stamp = Date.now();
  const rand = Math.floor(Math.random() * 100000);
  return `${prefix}-${stamp}-${rand}@example.com`;
}

async function registerUser(page: Page, prefix: string): Promise<void> {
  await page.goto("/");

  const isLoginPage = page.url().includes("/login");
  if (!isLoginPage) {
    await page.getByTestId("login-link").click();
  }

  await page.getByText("Sign Up").click();
  await page.getByTestId("name-input").fill("Support E2E User");
  await page.getByTestId("email-input").fill(uniqueEmail(prefix));
  await page.getByTestId("password-input").fill("SecurePass123!");
  await page.getByTestId("auth-submit-button").click();
  await expect(page).not.toHaveURL(/\/login/);
}

test("authenticated user can create and resolve support ticket from account", async ({ page }) => {
  page.on("dialog", async (dialog) => {
    await dialog.accept();
  });

  await registerUser(page, "support-flow");
  await page.goto("/account");

  await page.getByRole("main").getByRole("button", { name: "Support" }).click();
  await expect(page.getByText("Support Conversations")).toBeVisible();

  const issueText = `Need help with delivery ${Date.now()}`;
  const issueInput = page.getByPlaceholder("Describe your issue...");
  await issueInput.fill(issueText);
  await expect(issueInput).toHaveValue(issueText);
  await page.getByRole("button", { name: "New Request" }).click();

  const createdTicket = page.locator(".premium-card", { hasText: issueText }).first();
  await expect
    .poll(async () => {
      const text = await page.getByRole("main").textContent();
      return text ?? "";
    }, { timeout: 20000 })
    .toContain(issueText);
  await expect(createdTicket).toBeVisible();

  await createdTicket.getByTitle("Resolve ticket").click();
  await expect(createdTicket).toContainText("resolved");
});
