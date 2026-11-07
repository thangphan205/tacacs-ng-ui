import { expect, type Page, test } from "@playwright/test"

// The API is mocked: Alert History rows only exist after a rule fires, and the
// point here is how each stored `payload_snapshot` shape is rendered (#372).

const event = (
  id: string,
  rule_name: string,
  payload_snapshot: string | null,
  extra: Record<string, unknown> = {},
) => ({
  id,
  rule_id: `rule-${id}`,
  channel_id: null,
  channel_name: null,
  rule_name,
  rule_severity: "medium",
  triggered_at: "2026-11-07T04:37:18Z",
  created_at: "2026-11-07T04:37:18Z",
  status: "no_channel",
  error_message: null,
  payload_snapshot,
  ...extra,
})

const EVENTS = [
  event(
    "1",
    "[System] New Username Detected",
    JSON.stringify({
      rule: "[System] New Username Detected",
      new_usernames: ["alice", "bob"],
    }),
  ),
  event(
    "2",
    "[System] High Auth Failure Rate",
    JSON.stringify({
      rule: "[System] High Auth Failure Rate",
      fail_count: 11,
      window_minutes: 10,
    }),
  ),
  event(
    "3",
    "[System] TACACS Config Changed",
    JSON.stringify({
      rule: "[System] TACACS Config Changed",
      config_change_count: 1,
      window_minutes: 5,
      changes: [
        {
          action: "UPDATE",
          entity_id: null,
          by: "admin@example.com",
          at: "2026-11-07 04:33:17 UTC",
        },
      ],
    }),
  ),
  event("4", "[System] Old Event Without Details", null),
  event("5", "[System] Broken Payload", "not json {", {
    status: "failed",
    error_message: "Telegram: chat not found",
  }),
]

async function mockAlertApi(page: Page) {
  await page.route("**/api/v1/alert_events/statistics", (route) =>
    route.fulfill({
      json: {
        total: EVENTS.length,
        sent: 0,
        failed: 1,
        no_channel: 4,
        last_24h: EVENTS.length,
        by_severity: [{ severity: "medium", count: EVENTS.length }],
        by_rule: [],
      },
    }),
  )
  await page.route("**/api/v1/alert_events/?*", (route) =>
    route.fulfill({ json: { data: EVENTS, count: EVENTS.length } }),
  )
}

async function openDetails(page: Page, ruleName: string) {
  await page.goto("/alert_events")
  await page.getByRole("button", { name: `Show details of ${ruleName}` }).click()
  return page.getByRole("dialog")
}

test.beforeEach(async ({ page }) => {
  await mockAlertApi(page)
})

test("clicking a row shows which usernames triggered the alert", async ({
  page,
}) => {
  const dialog = await openDetails(page, "[System] New Username Detected")
  await expect(dialog.getByText("New usernames")).toBeVisible()
  await expect(dialog.getByText("alice")).toBeVisible()
  await expect(dialog.getByText("bob")).toBeVisible()
  // The rule name is the title; it is not repeated as a payload field.
  await expect(dialog.getByText("Rule", { exact: true })).toHaveCount(0)
})

test("counts and window are labelled", async ({ page }) => {
  const dialog = await openDetails(page, "[System] High Auth Failure Rate")
  await expect(dialog.getByText("Auth failures")).toBeVisible()
  await expect(dialog.getByText("11", { exact: true })).toBeVisible()
  await expect(dialog.getByText("Window (min)")).toBeVisible()
})

test("config changes render as a table", async ({ page }) => {
  const dialog = await openDetails(page, "[System] TACACS Config Changed")
  await expect(dialog.getByRole("columnheader", { name: "By" })).toBeVisible()
  await expect(dialog.getByRole("cell", { name: "admin@example.com" })).toBeVisible()
  await expect(dialog.getByRole("cell", { name: "UPDATE" })).toBeVisible()
})

test("an event without a stored payload says so", async ({ page }) => {
  const dialog = await openDetails(page, "[System] Old Event Without Details")
  await expect(
    dialog.getByText("No details were recorded for this alert."),
  ).toBeVisible()
})

test("an unparseable payload is shown raw, with the delivery error", async ({
  page,
}) => {
  const dialog = await openDetails(page, "[System] Broken Payload")
  await expect(dialog.getByText("not json {")).toBeVisible()
  await expect(dialog.getByText("Telegram: chat not found")).toBeVisible()
})

test("a row opens with the keyboard and Escape closes the dialog", async ({
  page,
}) => {
  await page.goto("/alert_events")
  const row = page.getByRole("button", {
    name: "Show details of [System] New Username Detected",
  })
  await row.focus()
  await page.keyboard.press("Enter")
  await expect(page.getByRole("dialog")).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(page.getByRole("dialog")).toBeHidden()
})
