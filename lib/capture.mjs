// Evidence capture: a real page at phone width (DPR 3), full-page PNG + measured boxes of given phrases.
// node lib/capture.mjs <url> <outdir> "<phrase 1>" "<phrase 2>" ...
import { chromium } from "playwright";
import fs from "node:fs";

const [url, out, ...phrases] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 430, height: 932 }, deviceScaleFactor: 3, locale: "en-US" });
await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(1500);
// drop cookie bars, sticky headers and audio players so they don't cover the text
await page.addStyleTag({ content: `[class*="cookie"],[id*="cookie"],[class*="consent"],header,[class*="sticky"],[class*="audio"]{display:none!important}` });
await page.waitForTimeout(500);
const boxes = await page.evaluate((phrases) => {
  const res = {};
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const nodes = []; let n;
  while ((n = walker.nextNode())) if (n.textContent.trim()) nodes.push(n);
  for (const ph of phrases) {
    for (const node of nodes) {
      const i = node.textContent.toLowerCase().indexOf(ph.toLowerCase());
      if (i < 0) continue;
      const r = document.createRange(); r.setStart(node, i); r.setEnd(node, i + ph.length);
      const rects = [...r.getClientRects()].map((b) => ({ x: b.x + scrollX, y: b.y + scrollY, w: b.width, h: b.height }));
      res[ph] = rects; break;
    }
  }
  const h1 = document.querySelector("h1");
  if (h1) { const b = h1.getBoundingClientRect(); res["__h1"] = [{ x: b.x + scrollX, y: b.y + scrollY, w: b.width, h: b.height }]; }
  return { boxes: res, width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight };
}, phrases);
await page.screenshot({ path: `${out}/page.png`, fullPage: true });
fs.writeFileSync(`${out}/boxes.json`, JSON.stringify({ url, dpr: 3, ...boxes }, null, 1));
console.log(JSON.stringify({ found: Object.keys(boxes.boxes), height: boxes.height }));
await browser.close();
