/**
 * Record the real documentation walkthrough:
 * upload company CSVs → analysis starts → high-level lineage → detailed audit
 * → leadership evidence book.
 *
 * Run while `make api` and `make live` are serving the app.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const APP_URL = process.env.DEMO_URL ?? "http://127.0.0.1:5173";
const HERE = fileURLToPath(new URL(".", import.meta.url));
const OUT = join(HERE, "raw");
const DATA = resolve(HERE, "../../../data/given");
const WIDTH = 1440;
const HEIGHT = 900;

const sleep = (ms) => new Promise((done) => setTimeout(done, ms));

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const context = await browser.newContext({
    viewport: { width: WIDTH, height: HEIGHT },
    recordVideo: { dir: OUT, size: { width: WIDTH, height: HEIGHT } },
  });
  const page = await context.newPage();
  const videoStart = Date.now();

  await page.goto(`${APP_URL}/?film=1`, { waitUntil: "networkidle" });
  await page.getByText("Drop the quarterly books here").waitFor();
  await sleep(1000);

  const storyStart = Date.now();
  await page.locator('input[type="file"]').first().setInputFiles([
    join(DATA, "sec_metrics.csv"),
    join(DATA, "product_segments.csv"),
    join(DATA, "geography.csv"),
    join(DATA, "user_segments.csv"),
  ]);

  await page.getByText(/Composing the leadership summary|Executive summary/)
    .waitFor({ timeout: 45_000 });
  await sleep(1200);
  await page.getByRole("button", { name: /Open the closer/ }).click();

  await page.getByText("analysis complete").waitFor({ timeout: 45_000 });
  await sleep(1800);
  await page.getByRole("button", { name: "Detailed audit" }).click();
  await sleep(2800);

  await page.getByRole("button", { name: "leadership memo" }).first().click();
  await sleep(2400);
  await page.getByRole("button", { name: "Evidence book" }).click();
  await sleep(2400);

  const storyEnd = Date.now();
  const video = page.video();
  await context.close();
  const videoPath = await video.path();
  await browser.close();

  writeFileSync(join(OUT, "meta.json"), JSON.stringify({
    video: videoPath,
    startOffsetSec: Math.max(0, (storyStart - videoStart) / 1000 - 0.6),
    durationSec: (storyEnd - storyStart) / 1000 + 0.6,
  }, null, 2));
  console.log("recorded:", videoPath);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
