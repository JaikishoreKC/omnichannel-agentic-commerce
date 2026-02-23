import { expect, type Page, test } from "@playwright/test";

function uniqueEmail(prefix: string): string {
  const stamp = Date.now();
  const rand = Math.floor(Math.random() * 100000);
  return `${prefix}-${stamp}-${rand}@example.com`;
}

async function registerUser(page: Page, prefix: string): Promise<void> {
  await page.getByTestId("name-input").fill("E2E User");
  await page.getByTestId("email-input").fill(uniqueEmail(prefix));
  await page.getByTestId("password-input").fill("SecurePass123!");
  await page.getByTestId("register-button").click();
  await expect(page.getByTestId("status-message")).toContainText("Account created");
}

async function addFirstProductToCart(page: Page): Promise<void> {
  await expect(page.getByTestId("add-to-cart-prod_001")).toBeVisible();
  await page.getByTestId("add-to-cart-prod_001").click();
  await expect(page.getByTestId("status-message")).toContainText("Added Running Shoes Pro to cart");
}

async function sendChat(page: Page, text: string): Promise<void> {
  const input = page.getByTestId("chat-input");
  const sendButton = page.getByTestId("chat-send-button");
  const countBadge = page.getByTestId("chat-message-count");
  await expect(page.getByTestId("chat-ready")).toContainText("connected");
  const initialCount = Number((await countBadge.textContent())?.split(" ")[0] ?? "0");
  for (let attempt = 0; attempt < 8; attempt += 1) {
    if ((await page.getByTestId("chat-ready").textContent())?.includes("connected") !== true) {
      await page.waitForTimeout(350);
      continue;
    }
    await expect(sendButton).toBeEnabled();
    await input.fill(text);
    await sendButton.click();
    const didSend = await expect
      .poll(async () => {
        const current = Number((await countBadge.textContent())?.split(" ")[0] ?? "0");
        return current > initialCount;
      })
      .toBeTruthy()
      .then(
        () => true,
        () => false,
      );
    if (didSend) {
      return;
    }
    await page.waitForTimeout(350);
  }
  throw new Error(`Chat send did not succeed for message: ${text}`);
}

test("guest cart survives account creation", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("session-id")).not.toContainText("initializing");

  await addFirstProductToCart(page);
  await expect(page.getByTestId("cart-item-count")).toContainText("1 items");

  await registerUser(page, "guest-cart-transfer");
  await expect(page.getByTestId("cart-list")).toContainText("Running Shoes Pro");
});

test("catalog product opens dedicated detail page", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("session-id")).not.toContainText("initializing");

  await page.getByTestId("view-product-prod_001").click();
  await expect(page).toHaveURL(/\/products\/prod_001$/);
  await expect(page.getByTestId("product-detail-page")).toBeVisible();
  await expect(page.getByTestId("product-detail-name")).toContainText("Running Shoes Pro");
  await expect(page.getByTestId("product-detail-description")).toContainText("High-performance running shoes");
  await expect(page.getByTestId("product-detail-variants")).toContainText("var_001");

  await page.getByTestId("detail-add-to-cart").click();
  await expect(page.getByTestId("status-message")).toContainText("Added Running Shoes Pro to cart");
  await expect(page.getByTestId("cart-item-count")).toContainText("1 items");

  await page.getByTestId("back-to-catalog").click();
  await expect(page).toHaveURL(/\/$/);
});

test("authenticated user can checkout from cart", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("session-id")).not.toContainText("initializing");

  await registerUser(page, "auth-checkout");
  await addFirstProductToCart(page);

  await page.getByTestId("checkout-button").click();
  await expect(page.getByTestId("status-message")).toContainText("Order created: order_");
});

test("chat-driven add to cart and checkout works", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("session-id")).not.toContainText("initializing");
  await registerUser(page, "chat-checkout");
  await page.reload();
  await expect(page.getByTestId("session-id")).not.toContainText("initializing");
  await expect(page.getByTestId("chat-ready")).toContainText("connected");

  await sendChat(page, "show me running shoes");
  await expect(page.getByTestId("chat-log")).toContainText("Top result");

  await sendChat(page, "add to cart");
  await expect(page.getByTestId("chat-log")).toContainText("Added item to cart");

  await sendChat(page, "checkout");
  await expect(page.getByTestId("chat-log")).toContainText("Checkout complete. Order");
});

test("chat history is restored after reload", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("session-id")).not.toContainText("initializing");
  await registerUser(page, "history-restore");
  await page.reload();
  await expect(page.getByTestId("session-id")).not.toContainText("initializing");
  await expect(page.getByTestId("chat-ready")).toContainText("connected");

  await sendChat(page, "show me running shoes");
  await expect(page.getByTestId("chat-log")).toContainText("Top result");

  await page.reload();
  await expect(page.getByTestId("session-id")).not.toContainText("initializing");
  await expect(page.getByTestId("chat-ready")).toContainText("connected");

  await expect
    .poll(async () => (await page.getByTestId("chat-log").textContent()) ?? "")
    .toContain("You: show me running shoes");
  await expect
    .poll(async () => (await page.getByTestId("chat-log").textContent()) ?? "")
    .toContain("Top result");
});

