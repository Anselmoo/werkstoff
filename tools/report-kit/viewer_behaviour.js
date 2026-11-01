// Behaviour checks for every viewer state the kit drives -- what a screenshot cannot show.
//
// usage: node viewer_behaviour.js <states.json> [checks] [--only name,...] [--light] [-v]
// Run through check_viewer_behaviour.py, which builds every state from committed demo data
// (scripts/ci/viewer-screenshots.json) and writes <states.json>. Each check is one defect
// that once shipped green:
//   more    every clamped HUD verdict has its own "more" button, and a real mouse click on
//           it opens the "Verdict" drawer (all: unset once made it pointer-events: none)
//   hash    a malformed fragment (#rule-100%-done) throws nothing and leaves the figure drawn
//   fail    a broken data island shows its failure on the FIRST screen, verdict hidden
//   deep    a #sec-*/card hash scrolls to it on a fresh load; a hash naming a figure item
//           selects it and keeps the page at the top with the drawer open
//   focus   Enter on a mark, then Escape: focus returns into the stage, never to <body>
//   search  the header search shows its count in the header (first screen)
//   smoke   hover shows a tooltip, click opens the drawer, Escape closes it, no console error
//   zeug    zeugnis mutation: "not checked" is shown in the row, the figure and the drawer
//   layout  at 1600x900 .. 390x844: no horizontal scroll, HUD/legend/hint/drawer disjoint,
//           and no drawer opened on load below 860px
// Exit 0 all pass, 1 any check failed.
const { chromium } = require("playwright");
const fs = require("fs");
const argv = process.argv.slice(2);
const states = JSON.parse(fs.readFileSync(argv[0], "utf8"));
const rest = argv.slice(1);
const only = rest.includes("--only") ? rest[rest.indexOf("--only") + 1].split(",") : null;
const checks = (rest[0] && !rest[0].startsWith("-") ? rest[0] : "more,hash,fail,deep,focus,search,layout,smoke,zeug").split(",");
const scheme = rest.includes("--light") ? "light" : "dark";
const verbose = rest.includes("-v");
const results = [];
const rec = (st, check, ok, detail) => { results.push({ st: st.name, check, ok, detail }); };
const url = (st, hash, q) => "file://" + st.html + (q !== undefined ? q : (st.query.split("#")[0] || "")) + (hash || "");
const stHash = (st) => (st.query.includes("#") ? "#" + st.query.split("#")[1] : "");

async function open(browser, st, opts = {}) {
  const ctx = await browser.newContext({ viewport: opts.vp || { width: 1600, height: 900 }, colorScheme: scheme });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e.message)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.goto(opts.file ? "file://" + opts.file + (opts.hash || "") : url(st, opts.hash !== undefined ? opts.hash : stHash(st)));
  await page.waitForTimeout(opts.wait || 700);
  return { ctx, page, errors };
}
const inter = (a, b) => a && b && a.w > 0 && b.w > 0 && a.x < b.x + b.w - 0.5 && b.x < a.x + a.w - 0.5 && a.y < b.y + b.h - 0.5 && b.y < a.y + a.h - 0.5;

(async () => {
  const browser = await chromium.launch();
  for (const st of states) {
    if (only && !only.includes(st.name) && !only.includes(st.plugin)) continue;
    if (checks.includes("more")) {
      const { ctx, page } = await open(browser, st);
      const r = await page.evaluate(() => {
        const out = [];
        for (const v of document.querySelectorAll(".rk-hud .verdict")) {
          const vis = v.getClientRects().length > 0;
          out.push({ vis, over: vis && v.scrollHeight > v.clientHeight + 1 });
        }
        const btns = [...document.querySelectorAll(".rk-hud-more")].filter((b) => !b.hidden && b.getClientRects().length).map((b) => { const r = b.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; });
        return { verdicts: out, btns };
      });
      const overflowing = r.verdicts.filter((v) => v.over).length;
      let ok = r.btns.length === overflowing, detail = `overflowing=${overflowing} buttons=${r.btns.length}`;
      if (r.btns.length) {
        await page.mouse.click(r.btns[0].x, r.btns[0].y);
        await page.waitForTimeout(300);
        const t = await page.evaluate(() => { const d = document.getElementById("rk-drawer"); return d && !d.hidden ? (d.querySelector("h2") || {}).textContent : null; });
        ok = ok && t === "Verdict"; detail += ` drawer=${t}`;
      }
      rec(st, "more", ok, detail);
      await ctx.close();
    }
    if (checks.includes("hash")) {
      const { ctx, page, errors } = await open(browser, st, { hash: "#rule-100%-done" });
      const n = await page.evaluate(() => { const f = document.getElementById("rk-figure"); if (!f) return -1; const c = f.querySelector("canvas"); return c && c.width > 50 ? 99 : f.querySelectorAll("*").length; });
      rec(st, "hash", errors.length === 0 && n > 5, `errors=${errors.length} ${errors[0] || ""} figureNodes=${n}`);
      await ctx.close();
    }
    if (checks.includes("fail")) {
      const src = fs.readFileSync(st.html, "utf8").replace(/(<script type="application\/json" id="report-data"[^>]*>)[\s\S]*?(<\/script>)/, "$1{ broken$2");
      const f = st.html.replace(/\.html$/, ".broken.html"); fs.writeFileSync(f, src);
      const { ctx, page } = await open(browser, st, { file: f });
      const r = await page.evaluate(() => {
        const el = [...document.querySelectorAll(".rk-fail")].find((e) => e.getClientRects().length);
        if (!el) return null;
        const b = el.getBoundingClientRect();
        const hud = [...document.querySelectorAll(".rk-hud .verdict")].filter((v) => v.getClientRects().length).map((v) => v.textContent.slice(0, 60));
        return { top: b.top, bottom: b.bottom, ih: innerHeight, text: el.textContent.slice(0, 80), hud };
      });
      const ok = !!r && r.top >= 0 && r.bottom <= r.ih + 1 && r.hud.length === 0;
      rec(st, "fail", ok, JSON.stringify(r));
      await ctx.close(); fs.unlinkSync(f);
    }
    if (checks.includes("deep")) {
      // ids below the stage: sections and finding cards
      const { ctx, page } = await open(browser, st, { hash: "" });
      const ids = await page.evaluate(() => {
        const stage = document.getElementById("rk-stage");
        const below = (e) => stage && !stage.contains(e);
        const secs = [...document.querySelectorAll(".rk-section[id]")].filter(below).map((e) => e.id);
        const fins = [...document.querySelectorAll("details.rk-finding[id]")].filter(below).map((e) => e.id);
        return { secs, fins };
      });
      await ctx.close();
      const targets = [ids.secs[ids.secs.length - 1], ids.fins[ids.fins.length - 1]].filter(Boolean);
      for (const id of targets) {
        const { ctx: c2, page: p2, errors } = await open(browser, st, { hash: "#" + id, wait: 1200 });
        const r = await p2.evaluate((id) => {
          const t = document.getElementById(id); const b = t.getBoundingClientRect();
          const drawer = document.getElementById("rk-drawer");
          return { top: Math.round(b.top), ih: innerHeight, sy: scrollY, maxed: scrollY >= document.documentElement.scrollHeight - innerHeight - 2, open: t.tagName === "DETAILS" ? t.open : null, hidden: !t.getClientRects().length, drawerOpen: drawer && !drawer.hidden };
        }, id);
        // A claimed id (figure selected it, drawer open, at top) also passes.
        const claimed = r.sy === 0 && r.drawerOpen && !id.startsWith("sec-");
        const ok = claimed || (r.top >= -2 && r.top < r.ih - 40 && (r.top < 140 || r.maxed) && r.sy > 0 && r.open !== false && !r.hidden);
        rec(st, "deep", ok && errors.length === 0, `${id} ${JSON.stringify(r)}${claimed ? " (claimed)" : ""}`);
        await c2.close();
      }
    }
    if (checks.includes("focus")) {
      const { ctx, page } = await open(browser, st);
      const sel = await page.evaluate(() => {
        const fig = document.getElementById("rk-figure");
        const el = [...fig.querySelectorAll('[tabindex="0"], button, a[href]')].find((e) => e.getClientRects().length);
        if (!el) return null;
        el.setAttribute("data-audit-first", "1");
        return el.getAttribute("aria-label") || el.textContent.slice(0, 40);
      });
      if (!sel) { rec(st, "focus", true, "no focusable mark"); await ctx.close(); continue; }
      await page.focus('[data-audit-first="1"]');
      await page.keyboard.press("Enter");
      await page.waitForTimeout(400);
      const opened = await page.evaluate(() => !document.getElementById("rk-drawer").hidden);
      await page.keyboard.press("Escape");
      await page.waitForTimeout(400);
      const r = await page.evaluate(() => { const a = document.activeElement; return { tag: a.tagName, key: a.getAttribute && a.getAttribute("data-rk-key"), label: a.getAttribute && (a.getAttribute("aria-label") || "").slice(0, 40), inStage: !!a.closest && !!a.closest("#rk-stage") }; });
      rec(st, "focus", opened && r.tag !== "BODY" && r.inStage, `mark="${sel}" opened=${opened} -> ${JSON.stringify(r)}`);
      await ctx.close();
    }
    if (checks.includes("search")) {
      const { ctx, page } = await open(browser, st);
      const term = await page.evaluate(() => {
        const fig = document.getElementById("rk-figure");
        const el = [...fig.querySelectorAll("[data-rk-key], [aria-label]")].find((e) => (e.getAttribute("aria-label") || e.textContent).trim().length > 3);
        const t = el ? (el.getAttribute("data-rk-text") || el.getAttribute("aria-label") || el.textContent).trim() : "a";
        return t.split(/[\s:,(]+/).find((w) => w.length >= 4) || t.slice(0, 4);
      });
      await page.fill("#rk-q", term);
      await page.waitForTimeout(500);
      const r = await page.evaluate(() => {
        const top = document.querySelector(".rk-top");
        const st = [...top.querySelectorAll('[role="status"]')].find((e) => e.textContent.trim() && e.getClientRects().length);
        const fig = document.getElementById("rk-figure");
        return { count: st ? st.textContent : null, dim: fig.querySelectorAll("[data-rk-dim]").length, marks: fig.querySelectorAll("[data-rk-key]").length, sy: scrollY };
      });
      rec(st, "search", !!r.count, `term=${term} ${JSON.stringify(r)}`);
      await ctx.close();
    }

    if (checks.includes("smoke")) {
      const { ctx, page, errors } = await open(browser, st);
      const box = await page.evaluate(() => {
        const fig = document.getElementById("rk-figure");
        const onScreen = (e) => { const b = e.getBoundingClientRect(); return b.width > 4 && b.height > 4 && b.top >= 0 && b.bottom <= innerHeight; };
        const unselected = (e) => e.getAttribute("aria-pressed") !== "true" && !(e.classList && (e.classList.contains("sel") || e.classList.contains("on")));
        const cands = [...fig.querySelectorAll("[data-rk-key]")].filter((e) => !/^(crumb|dim|mod):/.test(e.getAttribute("data-rk-key")));
        const el = cands.filter(onScreen).find(unselected) || cands.find(onScreen) || [...fig.querySelectorAll('canvas, [tabindex="0"]')].find(onScreen);
        if (!el) return null;
        const b = el.getBoundingClientRect();
        // the centre must actually hit this mark (or a child), not an overlay
        const cx = b.x + Math.min(b.width / 2, 20), cy = b.y + b.height / 2;
        const top = document.elementFromPoint(cx, cy);
        return { x: cx, y: cy, hits: !!top && (el === top || el.contains(top)), key: el.getAttribute("data-rk-key"), label: (el.getAttribute("aria-label") || el.textContent || "").slice(0, 40) };
      });
      if (!box) { rec(st, "smoke", errors.length === 0, "no mark on first screen; errors=" + errors.length); await ctx.close(); continue; }
      await page.mouse.move(box.x, box.y); await page.waitForTimeout(250);
      const tip = await page.evaluate(() => { const t = document.querySelector(".rk-tip"); return !!t && !t.hidden; });
      await page.keyboard.press("Escape"); await page.waitForTimeout(300);
      if (box.label.startsWith("Force-directed")) { await page.focus("#map"); await page.keyboard.press("ArrowRight"); await page.keyboard.press("Enter"); }
      else {
        // Closing the drawer re-lays the figure out: find the mark again before clicking.
        const at = box.key === null ? box : await page.evaluate((k) => { const e = [...document.querySelectorAll("#rk-figure [data-rk-key]")].find((x) => x.getAttribute("data-rk-key") === k); const b = e.getBoundingClientRect(); return { x: b.x + Math.min(b.width / 2, 20), y: b.y + b.height / 2 }; }, box.key);
        await page.mouse.click(at.x, at.y);
      }
      await page.waitForTimeout(400);
      const opened = await page.evaluate(() => { const d = document.getElementById("rk-drawer"); return !d.hidden && d.querySelector("h2") ? d.querySelector("h2").textContent : null; });
      await page.keyboard.press("Escape"); await page.waitForTimeout(400);
      const closed = await page.evaluate(() => document.getElementById("rk-drawer").hidden);
      const ok = errors.length === 0 && opened !== null && closed;
      rec(st, "smoke", ok, `mark="${box.label}" hitsCentre=${box.hits} tip=${tip} opened=${opened} closedOnEsc=${closed} errors=${errors.length} ${errors[0] || ""}`);
      await ctx.close();
    }
    if (checks.includes("zeug") && st.name === "burndown-viewer-mutation") {
      const { ctx, page } = await open(browser, st);
      const r = await page.evaluate(() => {
        const row = document.getElementById("module-src-stats-bootstrap.py");
        const svgLabel = [...document.querySelectorAll("#rk-figure [aria-label]")].map((e) => e.getAttribute("aria-label")).find((l) => l.startsWith("src/stats/bootstrap.py")) || "";
        return { row: row ? row.querySelector(".mut-figures").textContent : null, svgLabel };
      });
      await page.evaluate(() => { const r = [...document.querySelectorAll("#rk-figure [aria-label]")].find((e) => e.getAttribute("aria-label").startsWith("src/stats/bootstrap.py")); r.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
      await page.waitForTimeout(300);
      const drawer = await page.evaluate(() => document.getElementById("rk-drawer").textContent);
      const ok = /not checked 25 → 0/.test(r.row || "") && /not checked 25 to 0/.test(r.svgLabel) && /Not checked before → after\s*25 → 0/.test(drawer);
      rec(st, "zeug", ok, JSON.stringify({ row: (r.row || "").slice(-60), svg: r.svgLabel.slice(0, 120), drawerHas: /Not checked before → after/.test(drawer) }));
      await ctx.close();
    }
    if (checks.includes("layout")) {
      for (const vp of [[1600, 900], [1366, 768], [1280, 720], [1024, 768], [390, 844]]) {
        const { ctx, page } = await open(browser, st, { vp: { width: vp[0], height: vp[1] } });
        const r = await page.evaluate(() => {
          const box = (sel) => { const e = document.querySelector(sel); if (!e || !e.getClientRects().length || e.hidden || getComputedStyle(e).visibility === "hidden") return null; const b = e.getBoundingClientRect(); return { x: b.x, y: b.y, w: b.width, h: b.height }; };
          const wide = [...document.querySelectorAll("body *")].filter((e) => e.getClientRects().length && e.getBoundingClientRect().right > document.documentElement.clientWidth + 1 && !e.closest(".rk-tw, pre, .rk-figure, [style*='overflow']")).slice(0, 3).map((e) => e.tagName + "." + (e.className && e.className.baseVal === undefined ? e.className : "") + " r=" + Math.round(e.getBoundingClientRect().right));
          return { sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, hud: box(".rk-hud"), legend: box(".rk-legend-float"), hint: box(".rk-hint"), drawer: box("#rk-drawer:not([hidden])"), fig: box("#rk-figure"), wide };
        });
        const probs = [];
        if (r.sw > r.cw + 1) probs.push(`hscroll ${r.sw}>${r.cw} ${r.wide.join(" | ")}`);
        const ov = { hud: r.hud, legend: r.legend, hint: r.hint };
        const names = Object.keys(ov);
        for (let i = 0; i < names.length; i++) for (let j = i + 1; j < names.length; j++) if (inter(ov[names[i]], ov[names[j]])) probs.push(`${names[i]}∩${names[j]}`);
        if (r.drawer) for (const n of names) if (inter(ov[n], r.drawer)) probs.push(`${n}∩drawer`);
        if (vp[0] < 860 && r.drawer) probs.push("drawer open on load at phone width");
        rec(st, "layout", probs.length === 0, `${vp[0]}x${vp[1]} ${probs.join("; ")}`);
        await ctx.close();
      }
    }
  }
  await browser.close();
  const bad = results.filter((r) => !r.ok);
  for (const r of results) if (!r.ok || verbose) console.log((r.ok ? "ok   " : "FAIL ") + r.check.padEnd(7) + r.st.padEnd(34) + r.detail);
  const by = {};
  for (const r of results) { by[r.check] = by[r.check] || [0, 0]; by[r.check][r.ok ? 0 : 1]++; }
  console.log("summary", JSON.stringify(by));
  process.exit(bad.length ? 1 : 0);
})();
