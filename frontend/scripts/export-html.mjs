import puppeteer from 'puppeteer';
import { mkdir, writeFile } from 'fs/promises';
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
  await page.waitForSelector('main', { timeout: 10000 });
  await page.evaluate(() => document.documentElement.classList.remove('dark'));
  await new Promise(r => setTimeout(r, 2000));

  console.log('Extracting styles and DOM...');

  const html = await page.evaluate(() => {
    // Collect all stylesheets
    const styles = [];
    for (const sheet of document.styleSheets) {
      try {
        const rules = Array.from(sheet.cssRules || []);
        styles.push(rules.map(r => r.cssText).join('\n'));
      } catch (e) {
        // Cross-origin stylesheet, try to fetch via link href
        if (sheet.href) {
          styles.push(`/* Could not inline: ${sheet.href} */`);
        }
      }
    }

    // Get the full DOM
    const dom = document.documentElement.outerHTML;

    return { styles, dom };
  });

  // Also fetch any linked stylesheets that couldn't be read
  const linkedStyles = await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll('link[rel="stylesheet"]'));
    return links.map(l => l.href);
  });

  let fetchedCSS = '';
  for (const href of linkedStyles) {
    try {
      const response = await page.goto(href, { waitUntil: 'load', timeout: 5000 });
      if (response) {
        fetchedCSS += await response.text() + '\n';
      }
    } catch (e) {
      // ignore
    }
  }

  // Go back to the page to get updated DOM (in case navigation changed it)
  await page.goto(URL, { waitUntil: 'networkidle2', timeout: 30000 });
  await page.waitForSelector('main', { timeout: 10000 });
  await new Promise(r => setTimeout(r, 2000));

  const finalDOM = await page.evaluate(() => {
    // Remove all script tags
    const scripts = document.querySelectorAll('script');
    scripts.forEach(s => s.remove());

    // Remove all link[rel=stylesheet] tags (we'll inline them)
    const links = document.querySelectorAll('link[rel="stylesheet"]');
    links.forEach(l => l.remove());

    return document.documentElement.outerHTML;
  });

  // Build standalone HTML
  const standaloneHTML = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Translation App - UI Export</title>
  <style>
    ${html.styles.join('\n')}
    ${fetchedCSS}
  </style>
</head>
<body>
  ${finalDOM.replace(/<html[^>]*>/, '').replace(/<\/html>/, '').replace(/<head[\s\S]*?<\/head>/, '')}
</body>
</html>`;

  const outputPath = resolve(OUTPUT_DIR, 'ui-standalone.html');
  await writeFile(outputPath, standaloneHTML, 'utf-8');
  console.log(`Saved: ui-capture/ui-standalone.html (${(standaloneHTML.length / 1024).toFixed(0)} KB)`);

  await browser.close();
  console.log('Done!');
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
