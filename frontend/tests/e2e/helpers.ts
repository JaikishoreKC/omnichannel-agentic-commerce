import { createHmac } from "node:crypto";
import type { Page } from "@playwright/test";
import { expect } from "@playwright/test";

export function uniqueEmail(prefix: string): string {
  const stamp = Date.now();
  const rand = Math.floor(Math.random() * 100000);
  return `${prefix}-${stamp}-${rand}@example.com`;
}

export async function registerAndCompleteProfile(
  page: Page,
  options: {
    prefix: string;
    name?: string;
  },
): Promise<void> {
  const { prefix, name = "E2E User" } = options;
  await page.goto("/login");
  await page.getByText("Sign Up").click();
  await page.getByTestId("name-input").fill(name);
  await page.getByTestId("email-input").fill(uniqueEmail(prefix));
  await page.getByTestId("password-input").fill("SecurePass123!");
  await page.getByTestId("auth-submit-button").click();

  await expect(page).toHaveURL(/\/complete-profile$/);
  await page.getByTestId("profile-mobile-input").fill("+1 555 123 4567");
  await page.getByTestId("profile-line1-input").fill("123 Commerce Street");
  await page.getByTestId("profile-city-input").fill("Seattle");
  await page.getByTestId("profile-state-input").fill("WA");
  await page.getByTestId("profile-postal-input").fill("98101");
  await page.getByTestId("profile-country-input").fill("US");
  await page.getByRole("button", { name: "Save And Continue" }).click();
  await expect(page).toHaveURL("/");
}

function base32Decode(input: string): Buffer {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const normalized = input.toUpperCase().replace(/=+$/g, "").replace(/\s+/g, "");
  let bits = "";
  for (const char of normalized) {
    const index = alphabet.indexOf(char);
    if (index < 0) {
      continue;
    }
    bits += index.toString(2).padStart(5, "0");
  }
  const bytes: number[] = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) {
    bytes.push(parseInt(bits.slice(i, i + 8), 2));
  }
  return Buffer.from(bytes);
}

export function generateTotp(secret: string, timestampMs = Date.now()): string {
  const key = base32Decode(secret);
  const counter = Math.floor(timestampMs / 1000 / 30);
  const message = Buffer.alloc(8);
  message.writeUInt32BE(Math.floor(counter / 0x100000000), 0);
  message.writeUInt32BE(counter >>> 0, 4);
  const digest = createHmac("sha1", key).update(message).digest();
  const offset = digest[digest.length - 1] & 0x0f;
  const codeInt =
    ((digest[offset] & 0x7f) << 24)
    | (digest[offset + 1] << 16)
    | (digest[offset + 2] << 8)
    | digest[offset + 3];
  const code = (codeInt % 1_000_000).toString().padStart(6, "0");
  return code;
}