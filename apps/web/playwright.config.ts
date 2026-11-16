import { defineConfig } from "@playwright/test";
import { tmpdir } from "node:os";
import path from "node:path";
export default defineConfig({
  testDir: "./tests", testMatch: "v1_1.spec.ts", workers: 1, fullyParallel: false,
  timeout: 45000, globalTimeout: 240000, reporter: "list", outputDir: path.join(tmpdir(), "jous-v1_1-playwright-results"),
  use: { baseURL: "http://127.0.0.1:3009", channel: "msedge", trace: "off", screenshot: "off" },
});
