// Render the sections of specimen.html to PNG files, in a light and a dark theme.
// Needs Node, Playwright and Chrome: node specimen/render.cjs
const path = require('node:path');
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome' });
  const page = await (await browser.newContext({ viewport: { width: 1100, height: 900 }, deviceScaleFactor: 2 })).newPage();
  await page.goto('file://' + path.join(__dirname, 'specimen.html'));
  await page.evaluate(() => document.fonts.ready);
  for (const theme of ['light', 'dark']) {
    await page.evaluate(dark => document.documentElement.classList.toggle('dark', dark), theme === 'dark');
    for (const id of ['hero', 'sizes', 'glyphs', 'details']) {
      await page.locator('#' + id).screenshot({ path: path.join(__dirname, `${id}-${theme}.png`) });
    }
  }
  await browser.close();
})();
