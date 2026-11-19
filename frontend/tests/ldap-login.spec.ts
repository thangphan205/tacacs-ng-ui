import { expect, type Page, test } from "@playwright/test"
import { firstSuperuser, firstSuperuserPassword } from "./config.ts"

// The login page's LDAP tabs. The provider status is mocked, so these run in
// the normal stack without a directory server; real LDAP binds are covered by
// backend/tests (core/test_ldap_auth.py, api/routes/test_ldap_auth.py).

test.use({ storageState: { cookies: [], origins: [] } })

type ProvidersStatus = {
  google: boolean
  keycloak: boolean
  ldap: boolean
  microsoft: boolean
  passkey: boolean
  password_login: boolean
  open_registration: boolean
}

const mockStatus = async (page: Page, overrides: Partial<ProvidersStatus>) => {
  const status: ProvidersStatus = {
    google: false,
    keycloak: false,
    ldap: true,
    microsoft: false,
    passkey: false,
    password_login: true,
    open_registration: false,
    ...overrides,
  }
  await page.route("**/api/v1/auth-providers/status", (route) =>
    route.fulfill({ json: status }),
  )
}

/** Record LDAP sign-in requests and answer them with `respond`. */
const mockLdapLogin = async (
  page: Page,
  respond: { status: number; json: unknown },
) => {
  const bodies: URLSearchParams[] = []
  await page.route("**/api/v1/login/ldap/access-token", (route) => {
    bodies.push(new URLSearchParams(route.request().postData() ?? ""))
    return route.fulfill(respond)
  })
  return bodies
}

const ldapTab = (page: Page) => page.getByRole("tab", { name: "LDAP" })
const localTab = (page: Page) =>
  page.getByRole("tab", { name: "Local Account" })

test("Both tabs are shown and LDAP is selected first", async ({ page }) => {
  await mockStatus(page, {})
  await page.goto("/login")

  await expect(ldapTab(page)).toHaveAttribute("aria-selected", "true")
  await expect(localTab(page)).toHaveAttribute("aria-selected", "false")
  await expect(page.getByPlaceholder("Username")).toBeVisible()
  await expect(
    page.getByText("Sign in with your directory account."),
  ).toBeVisible()
  // LDAP has no local password reset.
  await expect(
    page.getByRole("link", { name: "Forgot password?" }),
  ).toHaveCount(0)
})

test("Only the active tab's form is in the page", async ({ page }) => {
  await mockStatus(page, {})
  await page.goto("/login")

  await localTab(page).click()
  await expect(page.getByPlaceholder("Email")).toBeVisible()
  await expect(
    page.getByRole("link", { name: "Forgot password?" }),
  ).toBeVisible()
  // One username/password pair for password managers, not two.
  await expect(page.getByPlaceholder("Username")).toHaveCount(0)
  await expect(page.getByPlaceholder("Password", { exact: true })).toHaveCount(
    1,
  )
})

test("The last tab used is remembered", async ({ page }) => {
  await mockStatus(page, {})
  await page.goto("/login")

  await localTab(page).click()
  await page.reload()
  await expect(localTab(page)).toHaveAttribute("aria-selected", "true")

  await ldapTab(page).click()
  await page.reload()
  await expect(ldapTab(page)).toHaveAttribute("aria-selected", "true")
})

test("Switching tabs does not move the form", async ({ page }) => {
  await mockStatus(page, {})
  await page.goto("/login")

  const positions = async () => ({
    heading: (await page.getByText("Login to your account").boundingBox())?.y,
    button: (await page.getByRole("button", { name: "Log In" }).boundingBox())
      ?.y,
  })
  await expect(page.getByPlaceholder("Username")).toBeVisible()
  const onLdap = await positions()
  await localTab(page).click()
  await expect(page.getByPlaceholder("Email")).toBeVisible()
  expect(await positions()).toEqual(onLdap)
})

test("LDAP sign-in uses the LDAP endpoint and opens the dashboard", async ({
  page,
  request,
}) => {
  // A real token, so the dashboard's own API calls succeed after sign-in.
  const tokenRes = await request.post("/api/v1/login/access-token", {
    form: { username: firstSuperuser, password: firstSuperuserPassword },
  })
  expect(tokenRes.ok()).toBeTruthy()
  const token = await tokenRes.json()

  await mockStatus(page, {})
  const ldapBodies = await mockLdapLogin(page, { status: 200, json: token })
  const localCalls: string[] = []
  page.on("request", (req) => {
    if (req.url().endsWith("/api/v1/login/access-token"))
      localCalls.push(req.url())
  })

  await page.goto("/login")
  await page.getByPlaceholder("Username").fill("jdoe")
  // Directory passwords follow the directory's policy, not the local
  // 8-character rule.
  await page.getByPlaceholder("Password", { exact: true }).fill("short")
  await page.getByRole("button", { name: "Log In" }).click()

  await page.waitForURL("/")
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible()
  expect(ldapBodies).toHaveLength(1)
  expect(ldapBodies[0].get("username")).toBe("jdoe")
  expect(ldapBodies[0].get("password")).toBe("short")
  // The local endpoint is never tried with a directory password.
  expect(localCalls).toHaveLength(0)
})

test("LDAP sign-in errors are shown", async ({ page }) => {
  await mockStatus(page, {})
  await mockLdapLogin(page, {
    status: 403,
    json: { detail: "Your directory account is not authorized to sign in." },
  })

  await page.goto("/login")
  await page.getByPlaceholder("Username").fill("outsider")
  await page.getByPlaceholder("Password", { exact: true }).fill("password")
  await page.getByRole("button", { name: "Log In" }).click()

  await expect(
    page.getByText("Your directory account is not authorized to sign in."),
  ).toBeVisible()
  await expect(page).toHaveURL(/\/login/)
})

test("LDAP form requires a username and a password", async ({ page }) => {
  await mockStatus(page, {})
  const ldapBodies = await mockLdapLogin(page, { status: 400, json: {} })

  await page.goto("/login")
  await page.getByRole("button", { name: "Log In" }).click()

  await expect(page.getByText("Username is required")).toBeVisible()
  await expect(page.getByText("Password is required")).toBeVisible()
  expect(ldapBodies).toHaveLength(0)
})

test("With local passwords off, only the LDAP form is shown", async ({
  page,
}) => {
  await mockStatus(page, { password_login: false })
  await page.goto("/login")

  await expect(page.getByPlaceholder("Username")).toBeVisible()
  await expect(page.getByRole("tablist")).toHaveCount(0)
  await expect(page.getByPlaceholder("Email")).toHaveCount(0)
})

test("With LDAP off, the local form is shown without tabs", async ({
  page,
}) => {
  await mockStatus(page, { ldap: false })
  await page.goto("/login")

  await expect(page.getByPlaceholder("Email")).toBeVisible()
  await expect(page.getByRole("tablist")).toHaveCount(0)
  await expect(page.getByPlaceholder("Username")).toHaveCount(0)
  // No hint line on the plain local page: it looks as it did before LDAP.
  await expect(page.getByText("Sign in with your local account.")).toHaveCount(
    0,
  )
})

test("With local passwords and LDAP both off, no form is shown", async ({
  page,
}) => {
  await mockStatus(page, { ldap: false, password_login: false, passkey: true })
  await page.goto("/login")

  await expect(
    page.getByRole("button", { name: "Sign in with a Passkey" }),
  ).toBeVisible()
  await expect(page.getByRole("button", { name: "Log In" })).toHaveCount(0)
  await expect(page.getByPlaceholder("Email")).toHaveCount(0)
  await expect(page.getByPlaceholder("Username")).toHaveCount(0)
})
