import type { ApiError } from "./api"
import { toaster } from "./components/ui/toaster"

export const emailPattern = {
  value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
  message: "Invalid email address",
}

export const namePattern = {
  value: /^[A-Za-z\s\u00C0-\u017F]{1,30}$/,
  message: "Invalid name",
}

export const passwordRules = (isRequired = true) => {
  const rules: any = {
    minLength: {
      value: 8,
      message: "Password must be at least 8 characters",
    },
  }

  if (isRequired) {
    rules.required = "Password is required"
  }

  return rules
}

export const newPasswordRules = (isRequired = true) => {
  const rules: any = {
    minLength: {
      value: 12,
      message: "Password must be at least 12 characters long.",
    },
    validate: {
      hasLower: (value: string) =>
        /[a-z]/.test(value) || "Must contain one lowercase letter.",
      hasUpper: (value: string) =>
        /[A-Z]/.test(value) || "Must contain one uppercase letter.",
      hasNumber: (value: string) =>
        /[0-9]/.test(value) || "Must contain one number.",
      hasSpecial: (value: string) =>
        /[!"#$%&'()*+,-./:;<=>?@[\\\]^_`{|}~]/.test(value) ||
        "Must contain one special character.",
    },
  }

  if (isRequired) {
    rules.required = "Password is required"
  }

  return rules
}

export const confirmPasswordRules = (
  getValues: () => any,
  isRequired = true,
) => {
  const rules: any = {
    validate: (value: string) => {
      const password = getValues().password || getValues().new_password
      return value === password ? true : "The passwords do not match"
    },
  }

  if (isRequired) {
    rules.required = "Password confirmation is required"
  }

  return rules
}

export const handleError = (err: ApiError) => {
  const errDetail = (err.body as any)?.detail
  let errorMessage = errDetail || "Something went wrong."
  if (Array.isArray(errDetail) && errDetail.length > 0) {
    errorMessage = errDetail[0].msg
  }
  toaster.create({
    title: "Something went wrong!",
    description: errorMessage,
    type: "error",
  })
}

/**
 * YYYY-MM-DD of `date` in `timeZone`, the browser's when omitted or unknown.
 * Log days are days in the log time zone (TacacsNgSetting.timezone, see
 * useLogDays), not the viewer's: an admin in another zone would otherwise ask
 * for the wrong day's log file around midnight. Never `toISOString()`, which
 * gives the UTC day (#356).
 */
export const toLocalISODate = (
  date: Date = new Date(),
  timeZone?: string,
): string => {
  if (timeZone) {
    try {
      const parts = new Intl.DateTimeFormat("en-US", {
        timeZone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).formatToParts(date)
      const get = (type: string) => parts.find((p) => p.type === type)?.value
      return `${get("year")}-${get("month")}-${get("day")}`
    } catch {
      // RangeError: unknown time zone; fall through to the browser's.
    }
  }
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, "0")
  const d = String(date.getDate()).padStart(2, "0")
  return `${y}-${m}-${d}`
}

/** A YYYY-MM-DD day `days` later (or earlier); calendar math, no time zone. */
export const shiftISODate = (isoDate: string, days: number): string => {
  const d = new Date(`${isoDate.slice(0, 10)}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}

/**
 * Label for a YYYY-MM-DD day. `new Date("2026-11-07")` is UTC midnight, which
 * the browser's local formatting shows as Nov 6 anywhere west of UTC.
 */
export const formatISODate = (
  isoDate: string,
  options: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" },
): string =>
  new Date(`${isoDate.slice(0, 10)}T00:00:00Z`).toLocaleDateString("en-US", {
    ...options,
    timeZone: "UTC",
  })

/**
 * A timestamp from the API, in the viewer's time zone with the zone named
 * (e.g. "11/7/2026, 17:08:12 GMT+7"), so admins in different zones can tell
 * which time they are reading. The API sends timestamps with an offset.
 */
export const formatDateTime = (
  value: string | number | Date | null | undefined,
  options: Intl.DateTimeFormatOptions = {},
  fallback = "—",
): string => {
  if (value === null || value === undefined || value === "") return fallback
  const d = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(d.getTime())) return fallback
  return d.toLocaleString("en-US", {
    hour12: false,
    timeZoneName: "short",
    ...options,
  })
}
