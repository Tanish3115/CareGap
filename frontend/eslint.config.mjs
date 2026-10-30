import { defineConfig, globalIgnores } from "eslint/config";
import next from "eslint-config-next/core-web-vitals";

export default defineConfig([
  ...next,
  // Existing data-loading effects intentionally synchronize with the API.
  { rules: { "react-hooks/set-state-in-effect": "off" } },
  globalIgnores([".next/**", "node_modules/**"]),
]);
