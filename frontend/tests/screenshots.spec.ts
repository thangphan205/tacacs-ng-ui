import { test } from "@playwright/test"

test.describe("Capture screenshots for README", () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test("Capture screenshots", async ({ page }) => {
    // Only run if the environment variable is explicitly set
    if (!process.env.CAPTURE_SCREENSHOTS) {
      test.skip()
      return
    }

    // Set a longer timeout for capturing all 20 screenshots
    test.setTimeout(120000)

    console.log("Starting screenshot capture...")

    // 1. Dashboard
    await page.goto("/")
    await page.waitForTimeout(3000)
    await page.screenshot({ path: "../img/dashboard.png" })
    console.log("Captured Dashboard.")

    // 2. TACACS Configs
    await page.goto("/tacacs_configs")
    await page.waitForTimeout(2500)
    await page.screenshot({ path: "../img/dashboard-tacacs-config.png" })
    console.log("Captured TACACS Configs.")

    // 3. Active Tacacs Config Dialog (Shows how to activate a config)
    try {
      console.log("Generating an inactive config file...")
      await page.locator('button:has-text("Generate Config")').click()
      await page.waitForTimeout(1000)
      // Explicitly fill the filename input
      await page.locator('input[placeholder="filename"]').fill("tac_plus-ng")
      // Blur the input to trigger validation for mode: "onBlur"
      await page.locator('input[placeholder="filename"]').blur()
      await page.waitForTimeout(1000)
      await page.locator('button[type="submit"]:has-text("Generate")').click()
      // Wait for the modal dialog to close completely (detached) to avoid pointer intercept errors
      await page.waitForSelector("text=Generate TACACS+ Config", {
        state: "detached",
      })
      await page.waitForTimeout(2000) // Additional timeout for table refresh and animations to settle

      // Click the filename button of the newly generated inactive config (first row)
      const configButton = page.locator("tbody tr td button").first()
      if (await configButton.isVisible()) {
        await configButton.click()
        await page.waitForTimeout(2000)
        await page.screenshot({ path: "../img/tacacs_config.png" })
        console.log("Captured Active Tacacs+ Config Dialog.")
        // Press Escape to close the dialog
        await page.keyboard.press("Escape")
        await page.waitForTimeout(1000)
      } else {
        console.log(
          "Could not find the filename button for Active Tacacs+ Config screenshot.",
        )
      }
    } catch (e) {
      console.error("Failed to capture Active Tacacs+ Config Dialog:", e)
    }

    // 4. Log Events Viewer
    await page.goto("/tacacs_logs")
    await page.waitForTimeout(2500)
    await page.screenshot({ path: "../img/tacacs-logs.png" })
    console.log("Captured Log Events Viewer.")

    // 5. AAA Statistics
    await page.goto("/aaa_statistics")
    await page.waitForTimeout(2500)
    await page.screenshot({ path: "../img/aaa-statistics.png" })
    console.log("Captured AAA Statistics.")

    // 6. Users Management (TACACS+ Users)
    await page.goto("/tacacs_users")
    await page.waitForTimeout(2500)
    await page.screenshot({ path: "../img/tacacs-users.png" })
    console.log("Captured Users Management.")

    // 7. Groups
    await page.goto("/tacacs_groups")
    await page.waitForTimeout(2500)
    await page.screenshot({ path: "../img/tacacs-groups.png" })
    console.log("Captured Groups.")

    // 8. Profiles
    await page.goto("/profiles")
    await page.waitForTimeout(2500)
    await page.screenshot({ path: "../img/profiles.png" })
    console.log("Captured Profiles.")

    // 9. Rulesets
    await page.goto("/rulesets")
    await page.waitForTimeout(2500)
    await page.screenshot({ path: "../img/rulesets.png" })
    console.log("Captured Rulesets.")

    // 10. Hosts
    await page.goto("/hosts")
    await page.waitForTimeout(2500)
    await page.screenshot({ path: "../img/hosts.png" })
    console.log("Captured Hosts.")

    // 11. Services
    await page.goto("/tacacs_services")
    await page.waitForTimeout(2500)
    await page.screenshot({ path: "../img/tacacs-services.png" })
    console.log("Captured Services.")

    // 12. Mavis
    await page.goto("/mavises")
    await page.waitForTimeout(2500)
    await page.screenshot({ path: "../img/mavises.png" })
    console.log("Captured Mavis.")

    // 13. TACACS+ NG Settings
    await page.goto("/tacacs_ng_settings")
    await page.waitForTimeout(2500)
    await page.screenshot({ path: "../img/tacacs-ng-settings.png" })
    console.log("Captured TACACS+ NG Settings.")

    // 14. Audit Logs
    await page.goto("/audit_logs")
    await page.waitForTimeout(2500)
    await page.screenshot({ path: "../img/audit-logs.png" })
    console.log("Captured Audit Logs.")

    // 15. Auth Providers
    await page.goto("/admin/auth-providers")
    await page.waitForTimeout(2500)
    await page.screenshot({ path: "../img/auth-providers.png" })
    console.log("Captured Auth Providers.")

    // 16. Configuration Options
    await page.goto("/configuration_options")
    await page.waitForTimeout(2500)
    await page.screenshot({ path: "../img/configuration-options.png" })
    console.log("Captured Configuration Options.")

    // 17. Admin Users Management
    await page.goto("/admin/users_management")
    await page.waitForTimeout(2500)
    await page.screenshot({ path: "../img/users-management.png" })
    console.log("Captured Admin Users Management.")

    // 18. API Docs (Swagger)
    try {
      await page.goto("http://localhost:8000/docs")
      await page.waitForTimeout(2500)
      await page.screenshot({ path: "../img/api.png" })
      console.log("Captured API Docs.")
    } catch (e) {
      console.error("Failed to capture API Docs:", e)
    }

    // 19. Traefik Dashboard
    try {
      await page.goto("http://localhost:8090/dashboard/")
      await page.waitForTimeout(3000)
      await page.screenshot({ path: "../img/traefik.png" })
      console.log("Captured Traefik.")
    } catch (e) {
      console.error("Failed to capture Traefik:", e)
    }

    // 20. Adminer Login
    try {
      await page.goto("http://localhost:8080")
      await page.waitForTimeout(2500)
      await page.screenshot({ path: "../img/adminer.png" })
      console.log("Captured Adminer.")
    } catch (e) {
      console.error("Failed to capture Adminer:", e)
    }

    console.log("Screenshot capture complete!")
  })
})
