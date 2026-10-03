import { execSync } from "node:child_process"
import path from "node:path"
import { tanstackRouter } from "@tanstack/router-plugin/vite"
import react from "@vitejs/plugin-react-swc"
import { defineConfig, loadEnv } from "vite"

// Paths the backend owns. The dev server proxies them so `npm run dev` is
// single-origin, matching what the frontend's nginx does in every container
// deployment — which is what lets the bundle use origin-relative URLs.
const backendPaths = ["/api", "/mcp", "/docs", "/redoc"]

// "branch@commit" shown in the UI. Docker builds have no .git in their context,
// so GIT_BRANCH / GIT_COMMIT arrive as build args; local builds ask git directly.
function git(args: string): string {
  try {
    return execSync(`git ${args}`, { stdio: ["ignore", "pipe", "ignore"] })
      .toString()
      .trim()
  } catch {
    return ""
  }
}

function buildInfo(): string {
  const branch = process.env.GIT_BRANCH || git("branch --show-current")
  const commit = process.env.GIT_COMMIT || git("rev-parse --short HEAD")
  if (!commit) return ""
  return branch ? `${branch}@${commit}` : commit
}

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Empty prefix so this picks up VITE_DEV_API_PROXY from .env without
  // exposing anything extra to the bundle.
  const env = loadEnv(mode, process.cwd(), "")
  const target = env.VITE_DEV_API_PROXY || "http://localhost:8000"

  return {
    define: {
      __BUILD_INFO__: JSON.stringify(buildInfo()),
    },
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      proxy: Object.fromEntries(
        backendPaths.map((p) => [p, { target, changeOrigin: true }]),
      ),
    },
    plugins: [
      tanstackRouter({
        target: "react",
        autoCodeSplitting: true,
      }),
      react(),
    ],
  }
})
