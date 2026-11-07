import { expect, type Page, test } from "@playwright/test"

// The API is mocked: the point is how the viewer handles a big file (#371),
// and the dev stack has no multi-thousand-line log to open.

const BIG = {
  id: "11111111-1111-1111-1111-111111111111",
  filename: "accounting-2026-11-06.log",
  filepath: "2026/11/accounting-2026-11-06.log",
  created_at: "2026-11-06T00:00:00Z",
  updated_at: "2026-11-06T00:00:00Z",
}
const SMALL = {
  ...BIG,
  id: "22222222-2222-2222-2222-222222222222",
  filename: "authorization-2026-11-06.log",
  filepath: "2026/11/authorization-2026-11-06.log",
}

const lines = (n: number, from = 0) =>
  Array.from(
    { length: n },
    (_, i) =>
      `2026-11-06 10:00:00 +0700 10.0.0.1 user${from + i} line ${from + i}\n`,
  ).join("")

const DOWNLOAD_BODY = lines(26070)

async function mockLogApi(page: Page) {
  await page.route("**/api/v1/tacacs_logs/files?*", (route) =>
    route.fulfill({ json: { data: [BIG, SMALL], count: 2 } }),
  )
  await page.route(`**/api/v1/tacacs_logs/${BIG.id}/download`, (route) =>
    route.fulfill({
      body: DOWNLOAD_BODY,
      headers: {
        "content-type": "text/plain; charset=utf-8",
        "content-disposition": `attachment; filename="${BIG.filename}"`,
      },
    }),
  )
  await page.route(
    new RegExp(`/api/v1/tacacs_logs/${BIG.id}(\\?.*)?$`),
    (route) =>
      route.fulfill({
        json: {
          ...BIG,
          data: lines(1000, 25070),
          total_lines: 26070,
          shown_lines: 1000,
        },
      }),
  )
  await page.route(
    new RegExp(`/api/v1/tacacs_logs/${SMALL.id}(\\?.*)?$`),
    (route) =>
      route.fulfill({
        json: { ...SMALL, data: lines(15), total_lines: 15, shown_lines: 15 },
      }),
  )
}

async function openFilesTab(page: Page) {
  await page.goto("/tacacs_logs")
  await page.getByRole("tab", { name: "Files" }).click()
}

test.beforeEach(async ({ page }) => {
  await mockLogApi(page)
})

test("a big file opens as plain text with a truncation note", async ({
  page,
}) => {
  await openFilesTab(page)
  await page.getByRole("button", { name: BIG.filename, exact: true }).click()

  const dialog = page.getByRole("dialog")
  await expect(dialog.getByTestId("log-truncation-note")).toHaveText(
    "Showing the last 1,000 of 26,070 lines. Download the file for the full content.",
  )
  const pre = dialog.getByTestId("log-plain-text")
  await expect(pre).toContainText("user26069 line 26069")
  // Plain text, not one highlighted span per token.
  expect(await pre.locator("span").count()).toBe(0)
})

test("a small file keeps highlighting and has no note", async ({ page }) => {
  await openFilesTab(page)
  await page.getByRole("button", { name: SMALL.filename, exact: true }).click()

  const dialog = page.getByRole("dialog")
  await expect(dialog.getByText("user14 line 14")).toBeVisible()
  await expect(dialog.getByTestId("log-truncation-note")).toHaveCount(0)
  await expect(dialog.getByTestId("log-plain-text")).toHaveCount(0)
})

test("the dialog downloads the whole file", async ({ page }) => {
  await openFilesTab(page)
  await page.getByRole("button", { name: BIG.filename, exact: true }).click()

  const downloadPromise = page.waitForEvent("download")
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Download" })
    .click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe(BIG.filename)
  const body = await (await download.createReadStream()).toArray()
  expect(Buffer.concat(body).toString()).toBe(DOWNLOAD_BODY)
})

test("each Files row has a download button", async ({ page }) => {
  await openFilesTab(page)
  const downloadPromise = page.waitForEvent("download")
  await page.getByRole("button", { name: `Download ${BIG.filename}` }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe(BIG.filename)
})
