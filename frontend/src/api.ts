import { client } from "./client/client.gen"

/**
 * The generated fetch client rejects with the parsed response body, which
 * carries no status code. `ApiError` restores the shape the app relies on —
 * `status` for the 401 auto-logout in `main.tsx`, `body` for `handleError()`.
 */
export class ApiError extends Error {
  readonly status: number
  readonly statusText: string
  readonly url: string
  readonly body: unknown

  constructor(body: unknown, response?: Response) {
    super(
      response
        ? `${response.status} ${response.statusText}`
        : "Network request failed",
    )
    this.name = "ApiError"
    this.status = response?.status ?? 0
    this.statusText = response?.statusText ?? ""
    this.url = response?.url ?? ""
    this.body = body
  }
}

export const apiBaseUrl = (): string => import.meta.env.VITE_API_URL

export const getAccessToken = (): string =>
  localStorage.getItem("access_token") || ""

client.setConfig({
  baseUrl: apiBaseUrl(),
  // The SDK marks bearer-protected operations via their `security` array; the
  // client turns the value returned here into the `Authorization` header.
  auth: () => getAccessToken(),
})

client.interceptors.error.use(
  (error, response) => new ApiError(error, response),
)
