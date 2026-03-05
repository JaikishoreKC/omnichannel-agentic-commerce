import { expect, type Page, test } from "@playwright/test";

function uniqueEmail(prefix: string): string {
  const stamp = Date.now();
  const rand = Math.floor(Math.random() * 100000);
  return `${prefix}-${stamp}-${rand}@example.com`;
}

async function registerAndLandOnProfileCompletion(page: Page, prefix: string): Promise<void> {
  await page.goto("/login");
  await page.getByText("Sign Up").click();

  await page.getByTestId("name-input").fill("Profile Flow User");
  await page.getByTestId("email-input").fill(uniqueEmail(prefix));
  await page.getByTestId("password-input").fill("SecurePass123!");
  await page.getByTestId("auth-submit-button").click();

  await expect(page).toHaveURL(/\/complete-profile$/);
  await expect(page.getByRole("heading", { name: "Complete Your Profile" })).toBeVisible();
}

test("registration requires profile completion before normal navigation", async ({ page }) => {
  await registerAndLandOnProfileCompletion(page, "profile-gate");

  await page.reload();
  await expect(page).toHaveURL(/\/complete-profile$/);

  await page.goto("/products");
  await expect(page).toHaveURL(/\/complete-profile$/);

  await page.getByTestId("profile-mobile-input").fill("+1 555 123 4567");
  await page.getByTestId("profile-line1-input").fill("123 Commerce Street");
  await page.getByTestId("profile-city-input").fill("Seattle");
  await page.getByTestId("profile-state-input").fill("WA");
  await page.getByTestId("profile-postal-input").fill("98101");
  await page.getByTestId("profile-country-input").fill("US");
  await page.getByRole("button", { name: "Save And Continue" }).click();

  await expect(page).toHaveURL("/");
  await page.goto("/products");
  await expect(page).toHaveURL(/\/products$/);
});

test("account settings profile edit persists", async ({ page }) => {
  await registerAndLandOnProfileCompletion(page, "profile-edit");

  await page.getByTestId("profile-mobile-input").fill("+1 555 000 1111");
  await page.getByTestId("profile-line1-input").fill("10 First Street");
  await page.getByTestId("profile-city-input").fill("Austin");
  await page.getByTestId("profile-state-input").fill("TX");
  await page.getByTestId("profile-postal-input").fill("78701");
  await page.getByTestId("profile-country-input").fill("US");
  await page.getByRole("button", { name: "Save And Continue" }).click();
  await expect(page).toHaveURL("/");

  await page.goto("/account");
  await page.getByRole("button", { name: "Settings" }).click();

  const mobileInput = page.getByTestId("account-mobile-input");
  await expect(mobileInput).toHaveValue("+1 555 000 1111");
  await mobileInput.fill("+1 555 222 3333");
  await page.getByRole("button", { name: "Save Profile" }).click();

  await expect(page.getByText("Profile updated successfully.")).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByTestId("account-mobile-input")).toHaveValue("+1 555 222 3333");
});
