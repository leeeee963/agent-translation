import puppeteer from 'puppeteer';
import { mkdir } from 'fs/promises';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUTPUT_DIR = resolve(__dirname, '../ui-capture');

const URL = 'http://localhost:8000';
const VIEWPORT = { width: 1920, height: 1080, deviceScaleFactor: 2 };

async function main() {
  await mkdir(OUTPUT_DIR, { recursive: true });

  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();
  await page.setViewport(VIEWPORT);

  // Force light mode
  await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'light' }]);

  console.log('Loading page...');
  await page.goto(URL, { waitUntil: 'networkidle2', timeout: 30000 });

  // Remove dark class if set
  await page.evaluate(() => document.documentElement.classList.remove('dark'));
  // Wait for React to render
  await page.waitForSelector('main', { timeout: 10000 });
  await new Promise(r => setTimeout(r, 2000));

  // Full page screenshot
  console.log('Taking full page screenshot...');
  await page.screenshot({
    path: resolve(OUTPUT_DIR, 'screenshot-full.png'),
    fullPage: true,
    type: 'png',
  });
  console.log('Saved: ui-capture/screenshot-full.png');

  // Viewport-only screenshot (above the fold)
  await page.screenshot({
    path: resolve(OUTPUT_DIR, 'screenshot-viewport.png'),
    fullPage: false,
    type: 'png',
  });
  console.log('Saved: ui-capture/screenshot-viewport.png');

  await browser.close();
  console.log('Done!');
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
