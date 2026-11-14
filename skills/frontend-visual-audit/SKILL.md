---
name: frontend-visual-audit
description: Exhaustive parallel-subagent VISUAL audit of a web frontend - capture every route, modal, popover, menu and form across viewports (mobile / desktop / wide), locales (incl. RTL) and user roles with headless Playwright, fan out vision-review subagents over the screenshots, verify the severe findings against the actual image, compose one ranked report, then STOP for the user before fixing. Use when asked to "visually audit the frontend", "check every page in every view/language/role", or "find all UI bugs".
---

# Frontend visual audit: capture -> review -> compose -> gate

Goal: a **complete, evidence-backed visual audit of the frontend** as real users meet it: every route, every overlay (modal, dialog, popover, dropdown, tooltip, toast), every form, at **three viewports** (mobile 390x844, desktop 1440x900, wide 1920x1080), in **every locale** (including RTL), for **every role** and the **logged-out** surface.

Findings are about what the eye sees: layout breakage, overflow and clipping, RTL mirroring, contrast and theming, spacing, alignment, truncation, broken images, z-index overlap, focus/hover states, empty/loading/error states, ergonomics, and pages a role can reach but should not (gating that leaks visually).

This is the one workflow in this setup that deliberately uses screenshots. Day-to-day UI verification uses text (accessibility snapshots, evaluated layout facts) because images are token-heavy.

**Do not edit product code in phases 1 to 3.**

## Prerequisites

- The app is running locally (default `http://localhost:3000`).
- Playwright is installed somewhere in the repo. Point `PLAYWRIGHT_FROM` at that package dir (e.g. `e2e/web`); the script resolves Playwright from there with `createRequire`, so you run it with plain `node` from anywhere.
- One saved Playwright `storageState` JSON per role (log each test account in once with your own setup script or `npx playwright codegen --save-storage`). Use dedicated audit accounts: if your app stores per-user preferences such as locale, a capture can change them; restore them afterwards so other test suites are not affected.

## Directories

```
.plan/visual-audit/state/<role>.json
.plan/visual-audit/shots/<role>/<locale>/<route>__<viewport>[__light][__ov-<label>].png
.plan/visual-audit/findings/<slice-id>.md
.plan/visual-audit/REPORT.md
```

`.plan/` is git-ignored. One review slice = one findings file = one subagent.

Findings file shape:

```markdown
# <slice-id>
scope: <roles/locales/viewports/routes reviewed>
screenshots-read: <count>
verdict: findings | clean

## V-<slice-id>-01
severity: critical | high | medium | low
category: layout | overflow | rtl | contrast | theming | spacing | truncation | broken-asset |
          overlap | state | focus-hover | gating-leak | ergonomics | i18n
evidence: <exact screenshot path>
viewport: mobile | desktop | wide | all
locale: <locale> | all
role: <role> | all
what: <the visual defect>
why: <who it hurts>
fix: <minimal change, and the component if known>
confidence: high | medium | low
```

## Phase 1: Capture

Copy `audit.config.example.json` to `.plan/visual-audit/config.json` and list your routes, roles, locales and overlay trigger texts. Then run one process per (role, locale); each launches its own Chromium, so they parallelise without contention:

```bash
export AUDIT_CONFIG=.plan/visual-audit/config.json PLAYWRIGHT_FROM=e2e/web
for role in admin member viewer; do
  for loc in en ar; do
    ROLE=$role STATE=.plan/visual-audit/state/$role.json LOCALE=$loc \
      node .claude/skills/frontend-visual-audit/capture.mjs &
  done
done
ROLE=anon STATE= LOCALE=en node .claude/skills/frontend-visual-audit/capture.mjs &
wait
```

Per (role, locale), `capture.mjs` opens every route at each viewport, waits for the app to settle, takes a full-page screenshot, then runs a bounded **overlay probe** inside the main content area (buttons matching the configured trigger texts, `aria-haspopup` menus) and screenshots any dialog, menu or popover that opens. It discovers one detail page per configured list route by following the first row link. A sampled set of routes is also captured in the secondary theme. A route a role cannot access should redirect; that redirect screenshot is itself evidence of gating.

The probe is best-effort. A reviewer that spots a missed modal may extend the config or run a one-off Playwright snippet for it; the goal is coverage.

**Never fan out a browser-automation MCP for this.** It is one shared browser; concurrent agents driving it corrupt each other. Capture is standalone `node` processes; review reads PNG files.

## Phase 2: Fan out vision review (read-only)

Split the shots into slices and launch one subagent per slice, in parallel:

- **role x locale** for the authenticated app, all viewports and themes.
- **RTL cross-cut**: the whole RTL locale set, reviewed only for mirroring, icon and chevron direction, alignment, number/date direction, truncation from the wrong side.
- **Responsive cross-cut**: the mobile set across roles: tap targets, overflow, nav collapse, sticky headers, tables on small screens.
- **Logged-out**: marketing pages and the auth funnel.

Each prompt names the exact shot directories, the review lens, the findings path and schema. Tell it: **read the actual PNGs, do not infer from file names**; write the file; return one line.

## Phase 3: Compose and gate

1. Read every findings file.
2. Dedupe (the same overflow appears in several role slices; collapse to one entry listing the affected cells).
3. **Verify each critical/high yourself** by opening the cited PNG and confirming the defect is real and correctly described.
4. Write `REPORT.md`: summary (counts by severity and category, worst screens), findings ranked by severity with evidence path, affected matrix cells and proposed fix, and coverage (cells captured, gaps).
5. **STOP.** Present the summary and wait for the user to choose what to fix.

## Phase 4: Fix and prove (after approval)

Fix approved findings (delegate independent screens to subagents), re-run `capture.mjs` for just the affected (role, locale), and compare before and after. Add a Playwright regression spec for anything worth locking in (RTL, mobile, a specific modal).

## Gotchas

- **Redirect is not broken.** A role that *renders* a forbidden page is the `gating-leak` finding.
- Know your locale's intended conventions before flagging them (for example, an RTL locale that deliberately uses Latin digits).
- Judge contrast against the primary theme first.
- `.plan/visual-audit/` is scratch: clear it once the fixes are released.
