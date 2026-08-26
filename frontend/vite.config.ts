import path from "node:path"
import { tanstackRouter } from "@tanstack/router-plugin/vite"
import react from "@vitejs/plugin-react-swc"
import { defineConfig, loadEnv } from "vite"

// Paths the backend owns. The dev server proxies them so `npm run dev` is
// single-origin, matching what the frontend's nginx does in every container
// deployment — which is what lets the bundle use origin-relative URLs.
const backendPaths = ["/api", "/mcp", "/docs", "/redoc"]

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Empty prefix so this picks up VITE_DEV_API_PROXY from .env without
  // exposing anything extra to the bundle.
  const env = loadEnv(mode, process.cwd(), "")
  const target = env.VITE_DEV_API_PROXY || "http://localhost:8000"

  return {
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
