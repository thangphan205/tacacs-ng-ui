import { expect, type Page, test } from "@playwright/test"
import { createUser } from "./utils/privateApi.ts"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

const randomKeyName = () =>
  `e2e-key-${Math.random().toString(36).substring(2, 10)}`

async function openApiKeysTab(page: Page) {
  await page.goto("/settings")
  await page.getByRole("tab", { name: "API Keys" }).click()
}

async function createKey(page: Page, name: string) {
  await page.getByRole("button", { name: "Create API Key" }).click()
  await page.getByPlaceholder("claude-desktop-laptop").fill(name)
  await page.getByRole("button", { name: "Create", exact: true }).click()
}

test("API Keys tab is visible to a superuser", async ({ page }) => {
  await page.goto("/settings")
  await expect(page.getByRole("tab", { name: "API Keys" })).toBeVisible()
})

test("Empty-state or table renders without error", async ({ page }) => {
  await openApiKeysTab(page)
  await expect(
    page.getByRole("button", { name: "Create API Key" }),
  ).toBeVisible()
})

test("Create dialog defaults to the three non-sensitive scopes", async ({
  page,
}) => {
  await openApiKeysTab(page)
  await page.getByRole("button", { name: "Create API Key" }).click()

  await expect(page.getByRole("checkbox", { name: /mcp:read/ })).toBeChecked()
  await expect(
    page.getByRole("checkbox", { name: /mcp:generate/ }),
  ).toBeChecked()
  await expect(
    page.getByRole("checkbox", { name: /mcp:validate/ }),
  ).toBeChecked()
  // mcp:secrets returns unmasked config, so it must never be on by default.
  await expect(
    page.getByRole("checkbox", { name: /mcp:secrets/ }),
  ).not.toBeChecked()
})

test("Name is required", async ({ page }) => {
  await openApiKeysTab(page)
  await page.getByRole("button", { name: "Create API Key" }).click()
  await page.getByRole("button", { name: "Create", exact: true }).click()

  await expect(page.getByText("Name is required.")).toBeVisible()
})

test("Created key is shown exactly once, then listed by prefix", async ({
  page,
}) => {
  const name = randomKeyName()
  await openApiKeysTab(page)
  await createKey(page, name)

  // Scope to the dialog: the table behind it also shows a truncated prefix.
  const dialog = page.getByRole("dialog")
  const secret = dialog.getByText(/^tngk_[\w-]+$/).first()
  await expect(secret).toBeVisible()
  const plaintext = (await secret.innerText()).trim()
  expect(plaintext).toMatch(/^tngk_[\w-]{20,}$/)

  await page.getByRole("button", { name: "Done" }).click()
  await expect(dialog).toHaveCount(0)

  const row = page.getByRole("row").filter({ hasText: name })
  await expect(row).toBeVisible()
  await expect(row.getByText("Active")).toBeVisible()

  // The full secret is never rendered again — only its 20-char prefix.
  await expect(page.getByText(plaintext, { exact: true })).toHaveCount(0)
  await expect(row.getByText(plaintext.slice(0, 20))).toBeVisible()
})

test("MCP Setup Guide button opens dialog with client tabs", async ({
  page,
}) => {
  await openApiKeysTab(page)
  await page.getByRole("button", { name: "MCP Setup Guide" }).click()

  const dialog = page.getByRole("dialog")
  await expect(dialog).toBeVisible()
  await expect(
    dialog.getByRole("heading", { name: "MCP Client Setup Guide" }),
  ).toBeVisible()
  await expect(dialog.getByRole("tab", { name: "Claude Code" })).toBeVisible()
  await expect(dialog.getByRole("tab", { name: "Claude Desktop" })).toBeVisible()
  await expect(dialog.getByRole("tab", { name: "Antigravity" })).toBeVisible()
  await expect(dialog.getByRole("tab", { name: "Gemini" })).toBeVisible()

  await dialog.getByRole("button", { name: "Close" }).click()
  await expect(dialog).toHaveCount(0)
})

test("Revoking a key marks it revoked and removes the revoke action", async ({
  page,
}) => {
  const name = randomKeyName()
  await openApiKeysTab(page)
  await createKey(page, name)
  await page.getByRole("button", { name: "Done" }).click()

  const row = page.getByRole("row").filter({ hasText: name })
  await row.getByRole("button", { name: "Revoke" }).click()
  await page.getByRole("button", { name: "Revoke", exact: true }).last().click()

  await expect(row.getByText("Revoked")).toBeVisible()
  await expect(row.getByRole("button", { name: "Revoke" })).toHaveCount(0)
})

test.describe("Non-superuser access", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("API Keys tab is hidden from a normal user", async ({ page }) => {
    const email = randomEmail()
    const password = randomPassword()
    await createUser({ email, password })
    await logInUser(page, email, password)

    await page.goto("/settings")
    await expect(page.getByRole("tab", { name: "My profile" })).toBeVisible()
    await expect(page.getByRole("tab", { name: "API Keys" })).toHaveCount(0)
  })
})
