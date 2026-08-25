import fs from "node:fs"
import { defineConfig } from "@hey-api/openapi-ts"

// The SDK's class and method names are derived from the OpenAPI `operationId`,
// which follows the `{tag}-{name}` convention (see CLAUDE.md). Since 0.99.0 the
// name builders receive only the operation id string, so the tag is read back
// out of the spec here to keep the generated names stable.
const spec = JSON.parse(fs.readFileSync("./openapi.json", "utf8"))
const tagByOperationId = new Map<string, string>()
for (const operations of Object.values(spec.paths as Record<string, unknown>)) {
  for (const operation of Object.values(
    operations as Record<string, { operationId?: string; tags?: string[] }>,
  )) {
    if (operation?.operationId) {
      tagByOperationId.set(operation.operationId, operation.tags?.[0] ?? "")
    }
  }
}

const pascalCase = (value: string): string =>
  value
    .split(/[^A-Za-z0-9]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join("")

const camelCase = (value: string): string => {
  const pascal = pascalCase(value)
  return pascal.charAt(0).toLowerCase() + pascal.slice(1)
}

export default defineConfig({
  input: "./openapi.json",
  output: "./src/client",

  plugins: [
    // `throwOnError` + the SDK's `responseStyle: "data"` make every call resolve
    // to the response body and reject on error, matching how the call sites and
    // TanStack Query are written.
    { name: "@hey-api/client-fetch", throwOnError: true },
    {
      name: "@hey-api/sdk",
      // `asClass` / `classNameBuilder` / `methodNameBuilder` / `operationId` are
      // deprecated in favour of `operations: { strategy: "byTags", ... }`. They
      // are kept because the replacement changes the generated *type* names
      // (`LoginLoginAccessTokenResponses` -> `PostApiV1LoginAccessTokenResponses`)
      // even when the class and method names come out identical. When migrating:
      // `operations.nesting` receives the IR operation, whose `id` is a
      // normalised `postApiV1LoginAccessToken` — the raw spec value is on
      // `operation.operationId`. Under `strategy: "byTags"` the container is
      // already supplied, so `nesting` must return just `[methodName]`.
      // NOTE: this doesn't allow tree-shaking
      asClass: true,
      operationId: true,
      paramsStructure: "flat",
      responseStyle: "data",
      classNameBuilder: "{{name}}Service",
      methodNameBuilder: (operationId: string) => {
        let name = camelCase(operationId)
        const service = pascalCase(tagByOperationId.get(operationId) ?? "")

        if (service && name.toLowerCase().startsWith(service.toLowerCase())) {
          name = name.slice(service.length)
          name = name.charAt(0).toLowerCase() + name.slice(1)
        }

        return name
      },
    },
    {
      name: "@hey-api/schemas",
      type: "json",
    },
  ],
})
