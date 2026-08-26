// Note: the `PrivateService` is only available when generating the client
// for local environments
import { PrivateService } from "../../src/client"
import { client } from "../../src/client/client.gen"

// These tests run under Node, so the client is configured here rather than
// through `src/api.ts`, which reads `import.meta.env`. It also needs an
// absolute URL: `VITE_API_URL` is empty by design (the bundle is
// origin-relative) and `fetch` cannot parse a relative one outside a browser.
client.setConfig({
  baseUrl: process.env.PLAYWRIGHT_API_URL || "http://localhost:8000",
})

export const createUser = async ({
  email,
  password,
}: {
  email: string
  password: string
}) => {
  return await PrivateService.createUser({
    privateUserCreate: {
      email,
      password,
      is_verified: true,
      full_name: "Test User",
    },
  })
}
