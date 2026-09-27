import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.BASE_URL ?? "http://localhost:8000";
// The Docker run mounts this directory, so keep its artifacts apart from local
// runs; otherwise a concurrent run wipes the other's test-results mid-flight.
const suffix = process.env.CI ? "-ci" : "";

// All specs share one SQLite database and each one resets it in setup,
// so the suite must run serially.
export default defineConfig({
  testDir: ".",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  outputDir: `test-results${suffix}`,
  reporter: [["list"], ["html", { open: "never", outputFolder: `playwright-report${suffix}` }]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    viewport: { width: 1600, height: 1000 },
  },
  projects: [
    { name: "api", testDir: "./api" },
    {
      name: "e2e",
      testDir: "./e2e",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1600, height: 1000 },
        // PW_CHANNEL=chrome runs against a locally installed Google Chrome
        // instead of Playwright's bundled Chromium.
        channel: process.env.PW_CHANNEL || undefined,
      },
    },
  ],
});
