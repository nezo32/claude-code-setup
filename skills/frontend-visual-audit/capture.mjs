// capture.mjs - headless visual capture for one (role, locale) across viewports.
//
// Env:
//   AUDIT_CONFIG     path to the JSON config (see audit.config.example.json)
//   PLAYWRIGHT_FROM  package dir that has playwright installed (e.g. e2e/web)
//   ROLE             role name for the output folder, or "anon"
//   STATE            Playwright storageState JSON for that role ('' = logged out)
//   LOCALE           locale code (e.g. en, ar)
//   OUTDIR           override the output dir
//   ROUTES           comma-separated override of the route list
//
// Run: ROLE=admin STATE=.plan/visual-audit/state/admin.json LOCALE=en \
//        node .claude/skills/frontend-visual-audit/capture.mjs
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const cwd = process.cwd();
const cfgPath = process.env.AUDIT_CONFIG ?? ".plan/visual-audit/config.json";
const CFG = JSON.parse(fs.readFileSync(cfgPath, "utf8"));

const pwFrom = path.resolve(cwd, process.env.PLAYWRIGHT_FROM ?? ".");
const require = createRequire(pathToFileURL(path.join(pwFrom, "package.json")).href);
const { chromium } = require("playwright");

const APP = (process.env.BASE_URL ?? CFG.baseUrl ?? "http://localhost:3000").replace(/\/$/, "");
const ROLE = process.env.ROLE ?? "anon";
const LOCALE = process.env.LOCALE ?? "en";
const STATE = process.env.STATE ?? "";
const PRIMARY = CFG.primaryTheme ?? "dark";
const SECONDARY = PRIMARY === "dark" ? "light" : "dark";
const OUT = process.env.OUTDIR ?? path.join(cwd, `.plan/visual-audit/shots/${ROLE}/${LOCALE}`);
fs.mkdirSync(OUT, { recursive: true });

const VIEWPORTS = Object.entries(CFG.viewports ?? { desktop: { width: 1440, height: 900 } });
const ROUTES = process.env.ROUTES
  ? process.env.ROUTES.split(",")
  : (STATE ? CFG.appRoutes : CFG.anonRoutes) ?? [""];
const SECONDARY_SAMPLE = new Set(CFG.lightSample ?? []);
const DETAIL_LISTS = new Set(CFG.detailFromLists ?? []);
const MAX_OVERLAYS = CFG.maxOverlaysPerPage ?? 8;

const slug = (r) => (r === "" ? "home" : r.replace(/[^a-zA-Z0-9-]+/g, "_"));
const urlFor = (route) =>
  CFG.localeInPath ? `${APP}/${LOCALE}${route ? "/" + route : ""}` : `${APP}${route ? "/" + route : ""}`;

async function settle(page) {
  try { await page.waitForLoadState("networkidle", { timeout: 8000 }); } catch {}
  try { await page.waitForTimeout(600); } catch {}
}

async function shoot(page, name) {
  const file = path.join(OUT, `${name}.png`);
  try { await page.screenshot({ path: file, fullPage: true, animations: "disabled" }); }
  catch { try { await page.screenshot({ path: file, animations: "disabled" }); } catch {} }
}

// Bounded overlay probe: open the page's OWN dialogs/menus (scoped to the content
// area so global header menus are not re-captured on every page) and snapshot them.
async function probeOverlays(page, base) {
  const scope = page.locator(CFG.contentSelector ?? "main").first();
  const root = (await scope.count().catch(() => 0)) ? scope : page.locator("body");
  const texts = (CFG.overlayTriggers ?? []).map((t) => `button:has-text("${t}")`);
  const triggers = root.locator(
    [...texts, '[aria-haspopup="menu"]', '[aria-haspopup="dialog"]',
      'button[aria-label*="menu" i]', 'button[aria-label*="actions" i]'].join(", ")
  );
  const n = Math.min(await triggers.count().catch(() => 0), MAX_OVERLAYS);
  const seen = new Set();
  for (let i = 0; i < n; i++) {
    try {
      const t = triggers.nth(i);
      if (!(await t.isVisible().catch(() => false))) continue;
      let label = ((await t.innerText().catch(() => "")) || (await t.getAttribute("aria-label").catch(() => "")) || `t${i}`)
        .trim().slice(0, 24).replace(/[^a-z0-9]+/gi, "-").toLowerCase().replace(/^-+|-+$/g, "") || `t${i}`;
      if (seen.has(label)) label = `${label}-${i}`;
      seen.add(label);
      await t.scrollIntoViewIfNeeded().catch(() => {});
      await t.click({ timeout: 2500 });
      await page.waitForTimeout(550);
      const overlay = page.locator(
        '[role="dialog"], [role="menu"], [role="listbox"], [role="alertdialog"], [role="tooltip"]'
      ).first();
      if (await overlay.isVisible().catch(() => false)) await shoot(page, `${base}__ov-${label}`);
      await page.keyboard.press("Escape").catch(() => {});
      await page.waitForTimeout(200);
      await page.keyboard.press("Escape").catch(() => {});
      await page.waitForTimeout(150);
    } catch {}
  }
}

async function captureViewport(browser, vpName, viewport, theme, routes) {
  const ctx = await browser.newContext({
    viewport,
    locale: LOCALE,
    colorScheme: theme,
    ...(STATE ? { storageState: STATE } : {}),
  });
  // Many theme libraries read localStorage("theme"); pin it.
  await ctx.addInitScript((t) => { try { localStorage.setItem("theme", t); } catch {} }, theme);
  const page = await ctx.newPage();
  const discovered = [];
  const isPrimaryDesktop = vpName === "desktop" && theme === PRIMARY;

  for (const route of routes) {
    try { await page.goto(urlFor(route), { waitUntil: "domcontentloaded", timeout: 20000 }); } catch {}
    await settle(page);
    const base = `${slug(route)}__${vpName}${theme !== PRIMARY ? "__" + theme : ""}`;
    await shoot(page, base);
    if (isPrimaryDesktop) await probeOverlays(page, base);

    if (isPrimaryDesktop && STATE && DETAIL_LISTS.has(route)) {
      const href = await page.locator(`a[href*="/${route}/"]`).first().getAttribute("href").catch(() => null);
      if (href && !/\/(new|create)$/.test(href)) discovered.push(href);
    }
  }

  if (theme === PRIMARY) {
    for (const href of [...new Set(discovered)]) {
      const url = href.startsWith("http") ? href : APP + href;
      try { await page.goto(url, { waitUntil: "domcontentloaded", timeout: 20000 }); } catch {}
      await settle(page);
      const base = `detail_${slug(href)}__${vpName}`;
      await shoot(page, base);
      if (vpName === "desktop") await probeOverlays(page, base);
    }
  }
  await ctx.close();
}

async function main() {
  const browser = await chromium.launch();
  try {
    for (const [vpName, viewport] of VIEWPORTS) {
      await captureViewport(browser, vpName, viewport, PRIMARY, ROUTES);
    }
    const sample = ROUTES.filter((r) => SECONDARY_SAMPLE.has(r));
    const desktop = CFG.viewports?.desktop ?? { width: 1440, height: 900 };
    if (sample.length) await captureViewport(browser, "desktop", desktop, SECONDARY, sample);
  } finally {
    await browser.close();
  }
  const files = fs.readdirSync(OUT).filter((f) => f.endsWith(".png"));
  console.log(`[${ROLE}/${LOCALE}] captured ${files.length} screenshots -> ${OUT}`);
}

main().catch((e) => { console.error(`[${ROLE}/${LOCALE}]`, e); process.exit(1); });
