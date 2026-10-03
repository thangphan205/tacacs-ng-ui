/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// Injected by vite.config.ts: "branch@commit", or "" when git info is unavailable.
declare const __BUILD_INFO__: string
