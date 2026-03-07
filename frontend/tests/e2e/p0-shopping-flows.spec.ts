import { expect, type Page, test } from "@playwright/test";
import { registerAndCompleteProfile } from "./helpers";

async function registerUser(page: Page, prefix: string): Promise<void> {
  await registerAndCompleteProfile(page, { prefix, name: "E2E User" });
}

async function addFirstProductToCart(page: Page): Promise<void> {
  await page.goto("/products");
  const addToCartButton = page.locator("[data-testid^='add-to-cart-']").first();
  await expect(addToCartButton).toBeVisible();
  await addToCartButton.click();
  await expect(page.getByTestId("cart-item-count")).toBeVisible();
}

async function sendChat(page: Page, text: string): Promise<void> {
  const chatInput = page.getByTestId("chat-input");
  const sendButton = page.getByTestId("chat-send-button");

  // Open chat if not open
  const isChatOpen = await page.getByTestId("chat-log").isVisible().catch(() => false);
  if (!isChatOpen) {
    await page.getByRole("button", { name: "Open chat assistant" }).click();
  }

  await expect(page.getByTestId("chat-ready")).toContainText("connected");

  await chatInput.fill(text);
  await sendButton.click();
  await expect(page.getByTestId("chat-log")).toContainText(text);
}

test("guest cart survives account creation", async ({ page }) => {
  await page.goto("/");
  await addFirstProductToCart(page);
  await expect(page.getByTestId("cart-item-count")).toContainText("1");

  await registerUser(page, "guest-cart-transfer");
  await page.goto("/cart");
  await expect(page.getByTestId("cart-list")).toBeVisible();
  // Should have at least one item
  const itemCount = await page.locator("[data-testid='cart-list'] > div").count();
  expect(itemCount).toBeGreaterThan(0);
});

test("catalog product opens dedicated detail page", async ({ page }) => {
  await page.goto("/");

  const productCard = page.locator("a[href^='/products/']").first();
  const productId = (await productCard.getAttribute("href"))?.split("/").pop();

  await productCard.click();
  await expect(page).toHaveURL(new RegExp(`/products/${productId}$`));

  // Verify detail page elements
  await expect(page.locator("h1")).toBeVisible();
  await expect(page.getByText("Add to Bag")).toBeVisible();
});

test("authenticated user can checkout from cart", async ({ page }) => {
  await page.goto("/products");
  await registerUser(page, "auth-checkout");
  await addFirstProductToCart(page);

  await page.goto("/cart");
  await page.getByTestId("checkout-button").click();
  await expect(page.getByTestId("confirm-checkout-button")).toBeVisible();
  await page.getByTestId("confirm-checkout-button").click();
  await expect(page).toHaveURL(/\/account/);
});

test("chat-driven interacton works", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Open chat assistant" })).toBeVisible();

  // Open chat
  await page.getByRole("button", { name: "Open chat assistant" }).click();
  await expect(page.getByTestId("chat-ready")).toContainText("connected");

  await sendChat(page, "show me running shoes");
  await expect
    .poll(async () => (await page.getByTestId("chat-log").textContent()) ?? "", { timeout: 20000 })
    .toMatch(/Top result|Assistant is thinking/i);
});

test("chat reconnects and accepts messages after reload", async ({ page }) => {
  await page.goto("/");
  await registerUser(page, "history-restore");
  await page.reload();
  await page.getByRole("button", { name: "Open chat assistant" }).click();
  await expect(page.getByTestId("chat-ready")).toContainText("connected");

  await sendChat(page, "show me running shoes");
  await expect
    .poll(async () => (await page.getByTestId("chat-log").textContent()) ?? "", { timeout: 20000 })
    .toContain("show me running shoes");

  await page.reload();
  await page.getByRole("button", { name: "Open chat assistant" }).click();
  await expect(page.getByTestId("chat-ready")).toContainText("connected");

  await sendChat(page, "show me running shoes");
  await expect(page.getByTestId("chat-log")).toContainText("show me running shoes");
});
