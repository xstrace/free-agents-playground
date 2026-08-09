/* free agent playground — 单页应用: 侧栏导航 + 右侧渲染 */
"use strict";
const META_URL = "data/meta.json";
let META = null;

/* ── 工具 ─────────────────────────────────────────── */
function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function inlineMd(s) {
  return esc(s)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<i>$2</i>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
}
function renderMd(text, compact) {
  const head = (lv, c) => compact ? `<p><b>${c}</b></p>` : `<h${lv}>${c}</h${lv}>`;
  const lines = String(text).split("\n");
  let out = [], i = 0, inCode = false, codeBuf = [];
  const itemRe = /^([-*]|\d+\.)\s+/;
  while (i < lines.length) {
    const line = lines[i];
    if (line.trim().startsWith("```")) {
      if (inCode) { out.push("<pre>" + codeBuf.join("") + "</pre>"); codeBuf = []; inCode = false; }
      else { inCode = true; }
      i++; continue;
    }
    if (inCode) { codeBuf.push(line + "\n"); i++; continue; }
    const s = line.trim();
    if (!s) { i++; continue; }
    let m = s.match(/^(#{1,4})\s+(.*)$/);
    if (m) { out.push(head(m[1].length, inlineMd(m[2]))); i++; continue; }
    if (itemRe.test(s)) {
      const ordered = /^\d+\.\s+/.test(s);
      const items = [];
      while (i < lines.length && itemRe.test(lines[i].trim())) {
        items.push("<li>" + inlineMd(lines[i].trim().replace(itemRe, "")) + "</li>");
        i++;
      }
      out.push(ordered ? "<ol>" + items.join("") + "</ol>" : "<ul>" + items.join("") + "</ul>");
      continue;
    }
    if (s.startsWith(">")) { out.push("<blockquote>" + inlineMd(s.replace(/^>/, "").trim()) + "</blockquote>"); i++; continue; }
    if (/^[-*_]{3,}$/.test(s)) { out.push("<hr>"); i++; continue; }
    const para = [inlineMd(s)];
    i++;
    while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|[-*]|\d+\.\s|>|```)/.test(lines[i].trim())) {
      para.push(inlineMd(lines[i].trim()));
      i++;
    }
    out.push("<p>" + para.join("<br>") + "</p>");
  }
  if (inCode) out.push("<pre>" + codeBuf.join("") + "</pre>");
  return out.join("\n");
}

/* ── 事件渲染 ─────────────────────────────────────── */
function renderBlocks(content) {
  if (typeof content === "string") return `<div class="body md">${renderMd(content, true)}</div>`;
  if (!Array.isArray(content)) return `<div class="body">${esc(content)}</div>`;
  return content.map(b => {
    if (!b || typeof b !== "object") return `<div class="body">${esc(b)}</div>`;
    const t = b.type;
    if (t === "text") return `<div class="body md">${renderMd(b.text || "", true)}</div>`;
    if (t === "thinking" || t === "reasoning") {
      return `<details><summary>思考</summary><div>${esc(b.text || "")}</div></details>`;
    }
    if (t === "toolCall") {
      const name = b.name || b.toolName || "?";
      let args = b.arguments || b.args || {};
      if (typeof args === "string") { try { args = JSON.parse(args); } catch (e) { args = { raw: args }; } }
      if (name === "bash" && args.command) {
        const cmd = String(args.command).trim();
        const shown = cmd.length <= 500 ? cmd : cmd.slice(0, 497) + "...";
        return `<div class="cmd"><span class="badge b-tool">bash</span><span class="prompt">$ </span>${esc(shown)}</div>`;
      }
      const keys = ["path", "file", "url", "query", "pattern", "dir", "filename", "name"];
      const summ = {};
      keys.forEach(k => { if (args[k] !== undefined) summ[k] = String(args[k]).slice(0, 120); });
      let extra = Object.keys(summ).length ? JSON.stringify(summ) : JSON.stringify(args);
      if (extra.length > 200) extra = extra.slice(0, 197) + "...";
      return `<div class="body code"><span class="badge b-tool">${esc(name)}</span> ${esc(extra)}</div>`;
    }
    if (t === "toolResult") {
      let data = b.data;
      if (typeof data === "object" && data !== null) data = JSON.stringify(data, null, 1);
      data = String(data);
      if (data.length > 800) data = data.slice(0, 797) + "...";
      return `<div class="body code"><span class="badge b-tool">结果</span> ${esc(data)}</div>`;
    }
    return `<div class="body">${esc(JSON.stringify(b).slice(0, 300))}</div>`;
  }).join("");
}
function eventHtml(r) {
  const ts = (r.timestamp || "").slice(11, 19);
  if (r.type !== "message") {
    if (r.type === "error") return `<div class="ev"><div class="head"><span class="t">${ts}</span><span class="badge b-err">错误</span></div><div class="body">${esc(JSON.stringify(r).slice(0, 400))}</div></div>`;
    if (r.type === "model_change") return `<div class="ev"><div class="head"><span class="t">${ts}</span><span class="badge b-tool">模型</span></div><div class="body">${esc(r.model || "?")}</div></div>`;
    return "";
  }
  const m = r.message || {};
  const role = m.role;
  if (role === "user") {
    const content = m.content;
    let text = "";
    if (Array.isArray(content)) text = content.filter(b => b && b.type === "text").map(b => b.text || "").join("");
    else text = String(content || "");
    // 系统/宿主注入的整段提示词(长文本)折叠展示, 不占版面
    if (text.trim().startsWith("# ") && text.length > 300) {
      const preview = text.trim().split("\n").slice(0, 3).join("\n");
      return `<div class="ev"><div class="head"><span class="t">${ts}</span><span class="badge b-sys">宿主注入</span></div><details><summary>展开系统提示词</summary><div>${esc(text)}</div></details></div>`;
    }
    return `<div class="ev"><div class="head"><span class="t">${ts}</span><span class="badge b-user">宿主</span></div>${renderBlocks(content)}</div>`;
  }
  if (role === "assistant") {
    const body = renderBlocks(m.content);
    if (!body.replace(/<[^>]+>/g, "").trim()) return "";
    return `<div class="ev"><div class="head"><span class="t">${ts}</span><span class="badge b-pi">Pi</span></div>${body}</div>`;
  }
  return `<div class="ev"><div class="head"><span class="t">${ts}</span><span class="badge b-tool">${esc(role)}</span></div>${renderBlocks(m.content)}</div>`;
}

/* ── 视图: 过程(按天) ─────────────────────────────── */
async function viewDay(day) {
  const res = await fetch(META.events[day]);
  const events = await res.json();
  document.getElementById("content").innerHTML =
    `<h2>${day} <span class="cnt">${events.length} 条事件</span></h2>
     <div class="hint">最新在前 · 宿主注入已折叠</div>
     ${events.map(eventHtml).join("")}`;
}

/* ── 视图: 日记(分天, 新→旧) ──────────────────────── */
function viewJournal() {
  const cards = META.journalDays.map((d, idx) =>
    `<details class="day-card" ${idx === 0 ? "open" : ""}>
       <summary><span class="d">${d.date}</span><span class="t">${esc(d.title)}</span></summary>
       <div class="md">${renderMd(d.content)}</div>
     </details>`).join("");
  document.getElementById("content").innerHTML =
    `<h2>📓 日记 <span class="cnt">${META.journalDays.length} 天 · 最新在前</span></h2>
     <div class="hint">按天归档, 点击展开</div>${cards}`;
}

/* ── 视图: 作品(文件树 + 右侧渲染) ─────────────────── */
function treeHtml(node, depth) {
  if (node.type === "dir") {
    return `<details ${depth < 1 ? "open" : ""}>
      <summary>📁 ${esc(node.name || "/")}</summary>
      <div class="dir-children">${(node.children || []).map(c => treeHtml(c, depth + 1)).join("")}</div>
    </details>`;
  }
  const icons = { md: "📄", img: "🖼", code: "⚙️", bin: "🗜" };
  const sz = node.size >= 1024 ? (node.size / 1024).toFixed(1) + " KB" : node.size + " B";
  return `<a data-art="${esc(node.url)}" data-kind="${node.kind}" data-name="${esc(node.name)}">
    <span>${icons[node.kind] || "🗜"} ${esc(node.name)}</span><span class="sz">${sz}</span></a>`;
}
async function viewArtifacts() {
  const root = META.artifacts;
  const pane = `<div class="hint">文件树 · 点击右侧渲染(可下载原文件)</div>`;
  document.getElementById("content").innerHTML =
    `<h2>📦 作品 <span class="cnt">${META.artCount} 个文件</span></h2>${pane}
     <div class="tree" id="art-tree">${(root.children || []).map(c => treeHtml(c, 0)).join("")}</div>
     <div id="art-view" style="margin-top:20px"></div>`;
  document.querySelectorAll("#art-tree a").forEach(a => {
    a.addEventListener("click", ev => {
      ev.preventDefault();
      document.querySelectorAll("#art-tree a").forEach(x => x.classList.remove("active"));
      a.classList.add("active");
      renderArtifact(a.dataset.art, a.dataset.kind, a.dataset.name);
    });
  });
}
async function renderArtifact(url, kind, name) {
  const box = document.getElementById("art-view");
  box.innerHTML = `<div class="hint">加载 ${esc(name)}…</div>`;
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("HTTP " + res.status);
    if (kind === "img") {
      box.innerHTML = `<div class="art-view"><img src="${esc(url)}" alt="${esc(name)}" style="max-width:100%;border-radius:10px"></div>`;
    } else {
      const text = await res.text();
      const body = kind === "md" ? renderMd(text) : `<div class="md"><pre>${esc(text.slice(0, 50000))}</pre></div>`;
      box.innerHTML = `<h2 style="margin-bottom:8px">${esc(name)}</h2>
        <div class="hint"><a href="${esc(url)}" download>下载原文件</a></div>${body}`;
    }
  } catch (e) {
    box.innerHTML = `<div class="ev"><span class="badge b-err">加载失败</span> ${esc(e.message)}</div>`;
  }
}

/* ── 侧栏 + 路由 ──────────────────────────────────── */
function sidebar() {
  const days = META.days.map(d => `<a data-nav="day" data-day="${d}"><span>${d}</span><span class="cnt">${META.evCount[d] || 0}</span></a>`).join("");
  document.getElementById("sidebar").innerHTML =
    `<div class="side-title">内容</div>
     <a data-nav="journal"><span>📓 日记</span></a>
     <a data-nav="artifacts"><span>📦 作品</span></a>
     <div class="side-title">过程 · 按天</div>
     ${days}
     <div class="side-foot" id="side-foot"></div>`;
  document.querySelectorAll("#sidebar a[data-nav]").forEach(a => {
    a.addEventListener("click", () => {
      const nav = a.dataset.nav;
      location.hash = nav === "journal" ? "#/journal" : nav === "artifacts" ? "#/artifacts" : `#/day/${a.dataset.day}`;
    });
  });
}
function route() {
  const h = location.hash;
  let cur = null;
  document.querySelectorAll("#sidebar a[data-nav]").forEach(a => {
    const nav = a.dataset.nav;
    const active = (nav === "journal" && h.startsWith("#/journal")) ||
      (nav === "artifacts" && h.startsWith("#/artifacts")) ||
      (nav === "day" && h === `#/day/${a.dataset.day}`);
    a.classList.toggle("active", active);
    if (active) cur = a;
  });
  if (cur) cur.scrollIntoView({ block: "nearest" });
  if (h.startsWith("#/journal")) viewJournal();
  else if (h.startsWith("#/artifacts")) viewArtifacts();
  else if (h.startsWith("#/day/")) viewDay(h.slice(6));
  else {
    location.hash = "#/journal";
    return;
  }
  const foot = document.getElementById("side-foot");
  if (foot) foot.innerHTML = `更新于 ${META.updated}<br>页面每 60 秒自动刷新`;
}
async function init() {
  try {
    const res = await fetch(META_URL);
    if (!res.ok) throw new Error("meta " + res.status);
    META = await res.json();
  } catch (e) {
    document.getElementById("content").innerHTML = `<div class="ev"><span class="badge b-err">加载失败</span> ${esc(e.message)}</div>`;
    return;
  }
  const chip = META.chip;
  document.getElementById("chip-slot").innerHTML =
    `<span class="chip ${chip.cls}">${esc(chip.text)}</span><span class="chip">${esc(META.updated)}</span>`;
  sidebar();
  route();
  window.addEventListener("hashchange", route);
}
init();
