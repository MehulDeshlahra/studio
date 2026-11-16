// Can the server capture a real Google Search / AI Mode answer? Phone viewport, DPR 3. Read-only.
// node lib/serp.mjs <outdir> "<query>" [udm]
import { chromium } from "playwright";
import fs from "node:fs";
const [out, q, udm] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 412, height: 915 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true, locale: "en-IN",
  userAgent: "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36",
});
const page = await ctx.newPage();
const url = `https://www.google.com/search?q=${encodeURIComponent(q)}&hl=en&gl=in${udm ? "&udm=" + udm : ""}`;
await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(9000);
const info = await page.evaluate(() => ({ title: document.title, text: document.body.innerText.slice(0, 600), url: location.href }));
await page.screenshot({ path: `${out}/serp.png`, fullPage: false });
fs.writeFileSync(`${out}/serp.json`, JSON.stringify(info, null, 1));
console.log(JSON.stringify(info).slice(0, 700));
await browser.close();
