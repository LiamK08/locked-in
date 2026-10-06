// Print booklet.html to an A3 PDF with Chromium via Playwright.
// usage: node print.js <in.html> <out.pdf>
const path = require('path');
const { chromium } = require('/opt/node-tools/node_modules/playwright');

(async () => {
  const [inHtml, outPdf] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + path.resolve(inHtml), { waitUntil: 'load' });
  await page.emulateMedia({ media: 'print' });
  await page.pdf({
    path: outPdf,
    preferCSSPageSize: true,
    printBackground: true,
    displayHeaderFooter: false,
  });
  await browser.close();
  console.log('wrote', outPdf);
})().catch(e => { console.error(e); process.exit(1); });
