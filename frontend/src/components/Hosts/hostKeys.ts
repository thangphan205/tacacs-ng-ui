/** Keys are written as `key = "<value>"`; the backend refuses these too. */
export const SAFE_KEY = {
  value: /^[^"\\\r\n]*$/,
  message: "Keys can't contain quotes, backslashes or line breaks.",
}
