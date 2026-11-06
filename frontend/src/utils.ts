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
 * YYYY-MM-DD of `date` in the browser's time zone. `toISOString()` gives the
 * UTC day, which west of UTC is already tomorrow every evening while the log
 * files are still on today (#356).
 */
export const toLocalISODate = (date: Date = new Date()): string => {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, "0")
  const d = String(date.getDate()).padStart(2, "0")
  return `${y}-${m}-${d}`
}
