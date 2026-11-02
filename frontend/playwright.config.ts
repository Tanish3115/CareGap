import { defineConfig } from "@playwright/test";
import path from "node:path";

const python = path.resolve(process.platform === "win32" ? "../backend/.venv/Scripts/python.exe" : "../backend/.venv/bin/python");
export default defineConfig({
  testDir: "./tests/e2e",
  workers: 1,
  timeout: 60000,
  use: { baseURL: "http://127.0.0.1:3100", trace: "retain-on-failure", screenshot: "only-on-failure" },
  webServer: [
    { command: `"${python}" "${path.resolve("../scripts/e2e_backend.py")}"`, url: "http://127.0.0.1:8100/health", timeout: 120000, reuseExistingServer: false },
    { command: "node node_modules/next/dist/bin/next dev --webpack -p 3100 -H 127.0.0.1", url: "http://127.0.0.1:3100", timeout: 120000, reuseExistingServer: false, env: { API_PROXY_TARGET: "http://127.0.0.1:8100", NEXT_DIST_DIR: ".next-e2e" } },
  ],
});
