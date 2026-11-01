/* werkstoff report kit -- shared behaviour for every plugins/<name>/assets/<name>-viewer.html.
 *
 * Source of truth; vendored per plugin as assets/report-kit.js (.rrt.toml
 * artifact_targets) and inlined by the builder at __REPORT_KIT__.
 *
 * Safety contract (report-viewer-standard S3), stated once and kept here:
 *   - data reaches the page only through createTextNode / textContent;
 *   - h() drops every attribute whose name starts with "on";
 *   - an href/src passes safeUrl(), an allow-list that fails closed;
 *   - nothing here assigns HTML strings to the DOM.
 * The builder is the first barrier (it escapes < > & in the JSON island); this
 * file is the second.
 *
 * Patterns adapted from anthropics/claude-plugins-official code-modernization
 * (report-template.html, topology-viewer.html; Apache-2.0) -- rewritten, not
 * copied. See tools/report-kit/README.md.
 */
/* exported RK */
const RK = (() => {
  "use strict";

  // ---- DOM ------------------------------------------------------------------
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (/^on/i.test(k)) continue; // never an inline handler
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = String(v);
      else if (k === "href" || k === "src") {
        const safe = safeUrl(String(v), k === "src");
        if (safe !== null) el.setAttribute(k, safe);
      } else el.setAttribute(k, v === true ? "" : String(v));
    }
    append(el, kids);
    return el;
  }

  function append(el, kids) {
    for (const kid of kids.flat(Infinity)) {
      if (kid === null || kid === undefined || kid === false) continue;
      el.appendChild(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }

  // Allow-list: in-page fragment, http(s), mailto, plain relative path; for
  // src additionally data:image/*. Control and invisible characters are
  // stripped first, so "java\tscript:" cannot slip through. Anything else is
  // refused (returns null) -- fail closed.
  function safeUrl(raw, isSrc) {
    const s = String(raw).replace(/[\u0000-\u001F\u007F-\u009F\u200B-\u200F\u2028-\u202E\u2060-\u206F\uFEFF]/g, "").trim();
    if (s === "" || /&#|&[a-z]+;/i.test(s)) return null;
    if (s.startsWith("#")) return s;
    if (isSrc && /^data:image\/(png|jpeg|gif|webp);base64,[A-Za-z0-9+/=]+$/.test(s)) return s;
    const scheme = /^([a-z][a-z0-9+.-]*):/i.exec(s);
    if (!scheme) return s.startsWith("//") ? null : s;
    return /^(https?|mailto)$/i.test(scheme[1]) && !isSrc ? s : null;
  }

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  // ---- data + failure ---------------------------------------------------------
  // Reads the JSON island. On a missing or unparseable island it renders a
  // visible failure naming the builder to re-run (S4) and returns null.
  function readData(rerun, id) {
    const node = document.getElementById(id || "report-data");
    try {
      const txt = node ? node.textContent.trim() : "";
      if (!txt || txt.startsWith("@@")) throw new Error("the data island is empty");
      return JSON.parse(txt);
    } catch (err) {
      fail("No report data in this file (" + err.message + ").", rerun);
      return null;
    }
  }

  function fail(message, rerun) {
    const target = $("#rk-content") || document.body;
    target.appendChild(h("div", { class: "rk-fail", role: "alert" },
      h("strong", { text: message }),
      rerun ? h("p", {}, "Re-run ", h("code", { text: rerun }), " to regenerate it.") : null));
  }

  // ---- tones ------------------------------------------------------------------
  const SEVERITY_TONE = {
    blocker: "bad", critical: "bad", high: "bad", error: "bad", fail: "bad", regressed: "bad",
    major: "warn", medium: "warn", warning: "warn", gap: "warn", partial: "warn",
    minor: "info", low: "info", info: "info", nit: "flat", na: "flat",
    pass: "ok", ok: "ok", done: "ok", proven: "ok",
    // Outcome words plugins already use, so a badge can keep its own word.
    broken: "bad", rejected: "bad", refused: "bad", missing: "bad", blocked: "bad", denied: "bad",
    unverified: "warn", contested: "warn", stale: "warn", dropped: "warn", malformed: "warn",
    verified: "ok", landed: "ok", accepted: "ok", met: "ok", linked: "ok", named: "ok",
    unmeasured: "flat", skipped: "flat", unknown: "flat", unrated: "flat",
  };
  const GLYPH = { ok: "✓", bad: "✗", warn: "!", info: "i", flat: "–" };
  const toneFor = (word) => SEVERITY_TONE[String(word || "").toLowerCase()] || "flat";

  // A badge always carries its word and a glyph; the tone colour is the third
  // channel, never the only one (R4).
  function badge(word, tone) {
    const t = tone || toneFor(word);
    return h("span", { class: "rk-badge " + t, title: String(word) }, GLYPH[t] + " " + word);
  }

  function copyButton(text, label) {
    const btn = h("button", { class: "rk-btn rk-copy", type: "button", "aria-label": label || "Copy" }, "Copy");
    btn.addEventListener("click", () => {
      const done = (msg) => { btn.textContent = msg; setTimeout(() => { btn.textContent = "Copy"; }, 1600); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => done("Copied"), () => done("Select and copy"));
      } else done("Select and copy");
    });
    return btn;
  }

  // ---- shell: theme, nav, search ------------------------------------------------
  function storeGet(k) { try { return localStorage.getItem(k); } catch (_) { return null; } }
  function storeSet(k, v) { try { localStorage.setItem(k, v); } catch (_) { /* private mode */ } }

  function initTheme() {
    const btn = $("#rk-theme");
    const saved = storeGet("rk-theme");
    if (saved === "light" || saved === "dark") document.documentElement.setAttribute("data-theme", saved);
    if (!btn) return;
    const current = () => document.documentElement.getAttribute("data-theme") ||
      (matchMedia && matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
    const label = () => { btn.textContent = current() === "light" ? "Dark" : "Light"; };
    label();
    btn.addEventListener("click", () => {
      const next = current() === "light" ? "dark" : "light";
      document.documentElement.setAttribute("data-theme", next);
      storeSet("rk-theme", next);
      label();
    });
  }

  // Builds the section nav from every .rk-section[id] carrying an <h2>, keeps
  // aria-current on the visible section, and mirrors it into a <select> that
  // replaces the list below 860px.
  function initNav() {
    const nav = $("#rk-nav");
    if (!nav) return;
    const sections = $$(".rk-section[id]").filter((s) => $("h2", s));
    const list = h("ul", {});
    const select = h("select", { class: "rk-select", "aria-label": "Jump to section" });
    for (const s of sections) {
      const title = $("h2", s).textContent;
      list.appendChild(h("li", {}, h("a", { href: "#" + s.id, "data-for": s.id, text: title })));
      select.appendChild(h("option", { value: s.id, text: title }));
    }
    select.addEventListener("change", () => { location.hash = select.value; });
    nav.prepend(list, select);
    if (!("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        for (const a of $$("a[data-for]", list)) a.setAttribute("aria-current", a.dataset.for === e.target.id ? "true" : "false");
        select.value = e.target.id;
      }
    }, { rootMargin: "0px 0px -70% 0px" });
    sections.forEach((s) => io.observe(s));
  }

  // Global search over every [data-rk-search] element: non-matching items hide,
  // matches are highlighted, and an aria-live line reports the count.
  function initSearch() {
    const q = $("#rk-q");
    if (!q) return;
    const found = $("#rk-found");
    let timer = 0;
    q.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(() => runSearch(q.value.trim(), found), 120);
    });
  }

  function clearMarks(root) {
    for (const m of $$("mark.rk-hit", root)) {
      const parent = m.parentNode;
      parent.replaceChild(document.createTextNode(m.textContent), m);
      parent.normalize();
    }
  }

  function markText(root, needle) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const hits = [];
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      if (n.nodeValue.toLowerCase().includes(needle)) hits.push(n);
    }
    for (const node of hits) {
      const text = node.nodeValue;
      const lower = text.toLowerCase();
      const frag = document.createDocumentFragment();
      let i = 0;
      for (let j = lower.indexOf(needle); j !== -1; j = lower.indexOf(needle, i)) {
        frag.appendChild(document.createTextNode(text.slice(i, j)));
        frag.appendChild(h("mark", { class: "rk-hit", text: text.slice(j, j + needle.length) }));
        i = j + needle.length;
      }
      frag.appendChild(document.createTextNode(text.slice(i)));
      node.parentNode.replaceChild(frag, node);
    }
  }

  // A viewer with its own filter (a matrix, a graph) registers here instead of
  // adding a second listener on #rk-q, so one box drives every view.
  const searchHooks = [];
  function onSearch(fn) { searchHooks.push(fn); }

  function runSearch(term, found) {
    // An item inside a hidden view (a tab not shown) is not a match the reader can see.
    const items = $$("[data-rk-search]").filter((el) => !(el.parentElement && el.parentElement.closest("[hidden]")));
    const needle = term.toLowerCase();
    let shown = 0;
    for (const el of items) {
      clearMarks(el);
      const match = !needle || el.textContent.toLowerCase().includes(needle);
      el.toggleAttribute("data-rk-nomatch", !match);
      applyVisibility(el);
      if (match) shown += 1;
      if (match && needle) {
        markText(el, needle);
        if (el.tagName === "DETAILS") el.open = true;
      }
    }
    if (found) found.textContent = needle ? `${shown} of ${items.length} match "${term}"` : "";
    for (const fn of searchHooks) fn(term);
  }

  // --header-h is a fallback constant (tokens.css says so); a sticky offset must
  // use the header's measured height, which changes when the header wraps.
  function syncHeaderHeight() {
    const top = $(".rk-top");
    if (!top) return;
    const set = () => document.documentElement.style.setProperty("--header-h", top.offsetHeight + "px");
    set();
    if ("ResizeObserver" in window) new ResizeObserver(set).observe(top);
    else window.addEventListener("resize", set);
  }

  // An item is visible only when no search and no facet filter excludes it.
  function applyVisibility(el) {
    el.hidden = el.hasAttribute("data-rk-nomatch") || el.hasAttribute("data-rk-filtered");
  }

  function init() {
    syncHeaderHeight();
    initTheme();
    initNav();
    initSearch();
    window.addEventListener("beforeprint", () => $$("details").forEach((d) => { d.open = true; }));
    if (location.hash) {
      const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (target && target.tagName === "DETAILS") target.open = true;
      if (target) target.scrollIntoView();
    }
  }

  // ---- components -----------------------------------------------------------------
  // glance({verdict, tone, stats:[{label, value, note, bad}], next:{command, why}})
  function glance(g) {
    const box = h("div", {});
    // The verdict is optional here: a page whose static .verdict line already
    // states it must not print it twice (R2) -- pass verdict: null.
    if (g.verdict) box.appendChild(h("p", { class: "rk-banner " + (g.tone || "flat") },
      h("strong", { text: (GLYPH[g.tone || "flat"] || "") + " " + g.verdict }),
      g.detail ? h("span", { class: "rk-muted", text: g.detail }) : null));
    if (g.stats && g.stats.length) {
      box.appendChild(h("dl", { class: "rk-stats" }, g.stats.map((s) =>
        // s.bad marks the number that needs action (R3); s.tone ("warn", "ok", "info")
        // gives a softer accent for a number to watch, never instead of its note.
        h("div", { class: "rk-stat" + (s.bad ? " bad" : s.tone ? " " + s.tone : "") },
          h("dt", { text: s.label }), h("dd", { text: s.value }),
          s.note ? h("small", { text: s.note }) : null))));
    }
    if (g.next && g.next.command) {
      box.appendChild(h("div", { class: "rk-card" },
        h("strong", { text: "Next step" }),
        h("div", { class: "rk-next" }, h("code", { text: g.next.command }), copyButton(g.next.command, "Copy the command")),
        g.next.why ? h("p", { class: "rk-muted", text: g.next.why }) : null));
    }
    return box;
  }

  // findings(list, opts) -- the common finding record:
  //   {id, severity, claim, file, line, quote, fix, evidence:[{label, detail, href}], tags:{k:v}}
  // opts.facets: tag/field names that get a filter bar when there are > 5 findings.
  // opts.order:  {field: [values in display order]} for the facet buttons and the sort.
  // opts.facetLabels: {field: "Shown label"} when the tag key is not reader-facing.
  function findings(list, opts) {
    const o = opts || {};
    const prefix = o.idPrefix || "finding-";
    const box = h("div", { class: "rk-findings" });
    if (!list.length) {
      box.appendChild(h("p", { class: "rk-banner ok", text: o.empty || "No findings." }));
      return box;
    }
    const sevOrder = (o.order && o.order.severity) || ["blocker", "critical", "high", "major", "medium", "minor", "low", "nit", "info"];
    const rank = (s) => { const i = sevOrder.indexOf(String(s).toLowerCase()); return i === -1 ? sevOrder.length : i; };
    // opts.sort: a comparator, for a plugin whose order is not severity (zeugnis puts
    // escalated findings first). Severity order stays the default.
    const sorted = list.slice().sort(o.sort || ((a, b) => rank(a.severity) - rank(b.severity)));
    const valueOf = (f, key) => (f.tags && key in f.tags ? f.tags[key] : f[key]);

    const cards = sorted.map((f, i) => {
      const id = prefix + String(f.id || i + 1).replace(/[^A-Za-z0-9_.-]/g, "-");
      const where = f.file ? f.file + (f.line ? ":" + f.line : "") : "";
      const card = h("details", { class: "rk-finding " + toneFor(f.severity), id, "data-rk-search": true },
        h("summary", {},
          // f.badge = {word, tone} keeps a plugin's own outcome word ("broken",
          // "landed") instead of forcing it into a severity.
          f.badge ? badge(f.badge.word, f.badge.tone) : badge(f.severity || "unrated"),
          f.rule ? h("code", { text: f.rule }) : null,
          h("span", { class: "rk-claim", text: f.claim || f.message || "(no claim recorded)" }),
          where ? h("span", { class: "rk-where mono", text: where }) : null,
          h("a", { class: "rk-permalink", href: "#" + id, title: "Link to this finding", text: "#" })),
        evidenceBody(f, where));
      for (const key of o.facets || []) card.setAttribute(facetAttr(key), String(valueOf(f, key) ?? ""));
      return card;
    });

    const active = {};
    const apply = () => {
      for (const c of cards) {
        const out = Object.entries(active).some(([k, set]) => set.size && !set.has(c.getAttribute(facetAttr(k))));
        c.toggleAttribute("data-rk-filtered", out);
        applyVisibility(c);
      }
    };
    if ((o.facets || []).length && list.length > 5) box.appendChild(filterBar(sorted, o, valueOf, active, apply));
    cards.forEach((c) => box.appendChild(c));
    // box.setFilter(key, values) lets a chart drive the same filter (a Sankey node,
    // a matrix cell) instead of re-implementing it beside the kit's bar.
    box.setFilter = (key, values) => {
      for (const c of cards) if (!c.hasAttribute(facetAttr(key))) c.setAttribute(facetAttr(key), "");
      active[key] = new Set((values || []).map(String));
      apply();
    };
    return box;
  }

  function evidenceBody(f, where) {
    const body = h("div", { class: "rk-body" });
    if (where) body.appendChild(h("p", {}, h("code", { text: where }), " ", copyButton(where, "Copy the location")));
    if (f.quote) body.append(h("h4", { text: "Quoted" }), h("pre", { text: f.quote }));
    if (f.fix) body.append(h("h4", { text: "Suggested fix" }), h("p", { text: f.fix }));
    if (f.evidence && f.evidence.length) {
      body.appendChild(h("h4", { text: "Evidence" }));
      body.appendChild(h("ul", {}, f.evidence.map((e) => h("li", {},
        e.href ? h("a", { href: e.href, text: e.label || e.href }) : h("strong", { text: e.label || "" }),
        e.detail ? " — " + e.detail : ""))));
    }
    if (!where && !f.quote && !f.fix && !(f.evidence && f.evidence.length)) {
      body.appendChild(h("p", { class: "rk-muted", text: "No evidence was recorded for this finding -- treat it as unverified." }));
    }
    return body;
  }

  // Any facet key (spaces included) maps to a valid attribute name.
  const facetAttr = (key) => "data-rk-facet-" + String(key).toLowerCase().replace(/[^a-z0-9_-]+/g, "-");

  function filterBar(sorted, o, valueOf, active, apply) {
    const bar = h("div", { class: "rk-filters", role: "group", "aria-label": "Filter findings" });
    for (const key of o.facets) {
      const values = Array.from(new Set(sorted.map((f) => String(valueOf(f, key) ?? ""))));
      const order = (o.order && o.order[key]) || values;
      values.sort((a, b) => order.indexOf(a) - order.indexOf(b));
      if (values.length < 2) continue;
      bar.appendChild(h("span", { class: "rk-label", text: (o.facetLabels && o.facetLabels[key]) || key }));
      for (const v of values) {
        const n = sorted.filter((f) => String(valueOf(f, key) ?? "") === v).length;
        const btn = h("button", { class: "rk-btn", type: "button", "aria-pressed": "false" }, `${v || "(none)"} · ${n}`);
        btn.addEventListener("click", () => {
          const on = btn.getAttribute("aria-pressed") !== "true";
          btn.setAttribute("aria-pressed", String(on));
          active[key] = active[key] || new Set();
          if (on) active[key].add(v); else active[key].delete(v);
          apply();
        });
        bar.appendChild(btn);
      }
    }
    return bar;
  }

  // table({columns:[{key, label, num}], rows:[{...}], caption}) -- sortable by header.
  function table(t) {
    const thead = h("tr", {}, t.columns.map((c) => h("th", { scope: "col", "aria-sort": "none", class: c.num ? "r" : null }, h("button", { type: "button", text: c.label }))));
    const tbody = h("tbody", {});
    const render = (rows) => {
      tbody.textContent = "";
      for (const r of rows) {
        tbody.appendChild(h("tr", { "data-rk-search": true }, t.columns.map((c) => {
          const v = r[c.key];
          const cell = v instanceof Node ? v : (c.badge ? badge(String(v ?? "")) : String(v ?? ""));
          return h("td", { class: c.num ? "r" : (c.mono ? "mono" : null) }, cell);
        })));
      }
    };
    render(t.rows);
    $$("th", thead).forEach((th, idx) => {
      $("button", th).addEventListener("click", () => {
        const col = t.columns[idx];
        const dir = th.getAttribute("aria-sort") === "ascending" ? "descending" : "ascending";
        $$("th", thead).forEach((o) => o.setAttribute("aria-sort", "none"));
        th.setAttribute("aria-sort", dir);
        const sign = dir === "ascending" ? 1 : -1;
        render(t.rows.slice().sort((a, b) => {
          // A Node cell sorts by its text unless the row gives <key>Sort.
          const key = (r) => (r[col.key + "Sort"] !== undefined ? r[col.key + "Sort"]
            : r[col.key] instanceof Node ? r[col.key].textContent : r[col.key]);
          const x = key(a), y = key(b);
          if (col.num) return sign * ((Number(x) || 0) - (Number(y) || 0));
          return sign * String(x ?? "").localeCompare(String(y ?? ""));
        }));
      });
    });
    return h("div", { class: "rk-tw", role: "region", tabindex: "0", "aria-label": t.caption || "table" },
      h("table", { class: "rk-table" }, t.caption ? h("caption", { class: "rk-sr", text: t.caption }) : null, h("thead", {}, thead), tbody));
  }

  // proof({verdict, headline, checks:[{label, state, detail}], notProven:[], needsPerson:[]})
  // verdict is PROVEN / PARTLY PROVEN / NOT PROVEN. needsPerson is a checklist
  // the model never ticks: it renders unchecked boxes only.
  function proof(p) {
    const tone = { "PROVEN": "ok", "PARTLY PROVEN": "warn", "NOT PROVEN": "bad" }[p.verdict] || "flat";
    const box = h("div", {});
    box.appendChild(h("p", { class: "rk-banner " + tone }, h("strong", { text: GLYPH[tone] + " " + p.verdict }), p.headline ? h("span", { text: p.headline }) : null));
    if (p.checks && p.checks.length) {
      box.appendChild(table({ caption: "checks", columns: [
        { key: "label", label: "Check" }, { key: "state", label: "State", badge: true }, { key: "detail", label: "Detail" }],
        rows: p.checks }));
    }
    if (p.notProven && p.notProven.length) {
      box.append(h("h3", { text: "What this does not prove" }), h("ul", {}, p.notProven.map((t) => h("li", { text: t }))));
    }
    if (p.needsPerson && p.needsPerson.length) {
      box.append(h("h3", { text: "Waiting for a person" }), h("ul", { class: "rk-checklist" }, p.needsPerson.map((t) => h("li", { text: t }))));
    }
    return box;
  }

  // beforeAfter({label, before, after, diff, note}) -- images must be data:image
  // URIs (CSP img-src data:). With both images a slider overlays them; the diff
  // image, when present, is shown beside.
  function beforeAfter(b) {
    const fig = (src, cap) => src ? h("figure", {}, h("img", { src, alt: cap + " -- " + (b.label || "") }), h("figcaption", { text: cap })) : null;
    const box = h("div", { class: "rk-card" }, h("strong", { text: b.label || "Before / after" }));
    if (b.before && b.after) {
      const after = h("img", { class: "rk-after", src: b.after, alt: "after -- " + (b.label || "") });
      const range = h("input", { type: "range", min: "0", max: "100", value: "50", "aria-label": "Reveal the after image" });
      range.addEventListener("input", () => { after.style.clipPath = `inset(0 0 0 ${range.value}%)`; });
      box.appendChild(h("div", { class: "rk-slider" }, h("img", { src: b.before, alt: "before -- " + (b.label || "") }), after));
      box.appendChild(range);
    }
    box.appendChild(h("div", { class: "rk-ba" }, fig(b.before, "before"), fig(b.after, "after"), fig(b.diff, "difference")));
    if (b.note) box.appendChild(h("p", { class: "rk-muted", text: b.note }));
    return box;
  }

  // value(v) -- any JSON value as readable structure: an object becomes a <dl>, an
  // array a <ul>, a scalar text. The R7 alternative to JSON.stringify in a <pre>.
  function value(v, depth) {
    const d = depth || 0;
    if (v === null || v === undefined) return h("span", { class: "rk-muted", text: "--" });
    if (Array.isArray(v)) {
      if (!v.length) return h("span", { class: "rk-muted", text: "none" });
      return h("ul", {}, v.map((x) => h("li", {}, value(x, d + 1))));
    }
    if (typeof v === "object") {
      if (d > 6) return h("code", { text: JSON.stringify(v) });
      return h("dl", { class: "rk-dl" }, Object.entries(v).map(([k, x]) => [h("dt", { text: k }), h("dd", {}, value(x, d + 1))]));
    }
    return document.createTextNode(String(v));
  }

  // section(id, title, ...kids) -- a nav-able, deep-linkable block.
  function section(id, title, ...kids) {
    return h("section", { class: "rk-section", id: "sec-" + id }, h("h2", { text: title }), ...kids);
  }

  return { h, append, safeUrl, $, $$, readData, fail, toneFor, badge, copyButton, init, onSearch, value, glance, findings, table, proof, beforeAfter, section };
})();
