"""The /judge dashboard's single HTML page. Kept apart from judge.py so the
routing logic stays readable; there is no template engine and no build step.

Grading is keyboard-first on purpose: ~40 queries x ~10 pooled candidates is
400-odd decisions, and reaching for the mouse each time is how judging sets get
abandoned half-finished.
"""

PAGE = """
<!doctype html>
<meta charset="utf-8">
<title>WADR - relevance judging</title>
<style>
  :root {
    --bg: #fbfbfa; --panel: #ffffff; --ink: #1a1a19; --muted: #6b6b66;
    --line: #e4e4e0; --accent: #2f6f4f; --accent-soft: #e8f2ec; --warn: #9a3b2f;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #16171a; --panel: #1d1f23; --ink: #e8e8e6; --muted: #9a9a94;
      --line: #2e3238; --accent: #6ec898; --accent-soft: #21332a; --warn: #d98b7f;
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink);
         font: 14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
  header { display: flex; align-items: center; gap: 16px; padding: 12px 18px;
           border-bottom: 1px solid var(--line); background: var(--panel);
           position: sticky; top: 0; z-index: 5; }
  header h1 { font-size: 15px; margin: 0; font-weight: 600; letter-spacing: -.01em; }
  .spacer { flex: 1; }
  .progress { color: var(--muted); font-variant-numeric: tabular-nums; }
  button { font: inherit; padding: 5px 11px; border: 1px solid var(--line);
           background: var(--panel); color: var(--ink); border-radius: 6px; cursor: pointer; }
  button:hover { border-color: var(--accent); }
  main { display: grid; grid-template-columns: 270px 1fr; min-height: calc(100vh - 53px); }
  aside { border-right: 1px solid var(--line); background: var(--panel);
          overflow-y: auto; max-height: calc(100vh - 53px); }
  .q { padding: 9px 14px; border-bottom: 1px solid var(--line); cursor: pointer;
       display: flex; gap: 8px; align-items: baseline; }
  .q:hover { background: var(--accent-soft); }
  .q.on { background: var(--accent-soft); box-shadow: inset 3px 0 0 var(--accent); }
  .q .qid { color: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
  .q .txt { flex: 1; word-break: break-word; }
  .badge { font-size: 11px; color: var(--muted); }
  .badge.has { color: var(--accent); font-weight: 600; }
  section { padding: 18px 22px; }
  .qhead { font-size: 17px; font-weight: 600; margin: 0 0 4px; }
  .hint { color: var(--muted); margin: 0 0 16px; }
  .cand { border: 1px solid var(--line); border-radius: 8px; background: var(--panel);
          padding: 12px 14px; margin-bottom: 9px; }
  .cand.sel { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft); }
  .cand .fn { font-weight: 600; word-break: break-word; }
  .cand .snip { color: var(--muted); margin: 5px 0 9px; font-size: 13px;
                max-height: 3.2em; overflow: hidden; }
  .chips { display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 9px; }
  .chip { font-size: 11px; padding: 1px 7px; border-radius: 99px;
          border: 1px solid var(--line); color: var(--muted); }
  .grades { display: flex; gap: 6px; }
  .grades button.on { background: var(--accent); border-color: var(--accent); color: #fff; }
  table { border-collapse: collapse; margin-top: 10px; }
  th, td { padding: 5px 12px; border-bottom: 1px solid var(--line); text-align: right;
           font-variant-numeric: tabular-nums; }
  th:first-child, td:first-child { text-align: left; }
  .err { color: var(--warn); }
  dialog { border: 1px solid var(--line); border-radius: 10px; background: var(--panel);
           color: var(--ink); padding: 18px; max-width: 640px; }
  dialog::backdrop { background: rgba(0, 0, 0, .35); }
</style>

<header>
  <h1>WADR relevance judging</h1>
  <span class="progress" id="progress"></span>
  <span class="spacer"></span>
  <button id="addBtn">+ query</button>
  <button id="benchBtn">Run benchmark</button>
</header>

<main>
  <aside id="queries"></aside>
  <section id="panel"><p class="hint">Pick a query on the left.</p></section>
</main>

<dialog id="bench">
  <div id="benchBody"></div>
  <p><button id="benchClose">Close</button></p>
</dialog>

<script>
let queries = [], current = null, candidates = [], selected = 0;

async function api(url, opts) {
  const r = await fetch(url, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || r.statusText);
  return body;
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
  });
}

async function loadQueries() {
  queries = await api("/judge/api/queries");
  const graded = queries.filter(function (q) { return q.graded > 0; }).length;
  document.getElementById("progress").textContent =
    graded + " of " + queries.length + " queries graded";
  document.getElementById("queries").innerHTML = queries.map(function (q) {
    return '<div class="q' + (current === q.qid ? " on" : "") + '" data-qid="' + esc(q.qid) + '">' +
      '<span class="qid">' + esc(q.qid) + "</span>" +
      '<span class="txt">' + esc(q.query) + "</span>" +
      '<span class="badge' + (q.graded ? " has" : "") + '">' + (q.graded || "") + "</span>" +
      "</div>";
  }).join("");
}

function currentQueryText() {
  const q = queries.find(function (x) { return x.qid === current; });
  return q ? q.query : "";
}

function render() {
  document.getElementById("panel").innerHTML =
    '<h2 class="qhead">' + esc(currentQueryText()) + "</h2>" +
    '<p class="hint">' + candidates.length + " pooled candidates &middot; " +
      "keys <b>0-3</b> grade the selected card and advance, <b>j</b>/<b>k</b> move &middot; " +
      "<b>0</b> means not relevant &middot; " +
      '<button id="delBtn">delete query</button></p>' +
    (candidates.length
      ? candidates.map(function (c, i) {
          return '<div class="cand' + (i === selected ? " sel" : "") + '" id="c' + i + '">' +
            '<div class="fn">' + esc(c.filename) + "</div>" +
            '<div class="snip">' + esc(c.snippet) + "</div>" +
            '<div class="chips">' +
              (c.found_by.length
                ? c.found_by.map(function (m) {
                    return '<span class="chip">' + esc(m) + "</span>";
                  }).join("") +
                  '<span class="chip">best rank ' + c.best_rank + "</span>"
                : '<span class="chip">graded earlier, not retrieved now</span>') +
            "</div>" +
            '<div class="grades">' + [0, 1, 2, 3].map(function (g) {
              return '<button class="' + (c.grade === g ? "on" : "") +
                '" data-i="' + i + '" data-g="' + g + '">' + g + "</button>";
            }).join("") + "</div>" +
          "</div>";
        }).join("")
      : '<p class="hint">No model returned anything for this query.</p>');
}

async function openQuery(qid) {
  current = qid;
  selected = 0;
  const panel = document.getElementById("panel");
  panel.innerHTML = '<p class="hint">Pooling results from all five models...</p>';
  await loadQueries();
  try {
    const data = await api("/judge/api/pool/" + encodeURIComponent(qid));
    candidates = data.candidates;
  } catch (e) {
    panel.innerHTML = '<p class="err">' + esc(e.message) + "</p>";
    return;
  }
  render();
}

async function setGrade(i, g) {
  candidates[i].grade = g;
  render();
  try {
    await api("/judge/api/grade", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ qid: current, file_hash: candidates[i].file_hash, grade: g }),
    });
  } catch (e) {
    alert(e.message);
  }
  loadQueries();
}

document.addEventListener("click", async function (ev) {
  const row = ev.target.closest(".q");
  if (row) { openQuery(row.dataset.qid); return; }

  const gradeBtn = ev.target.closest(".grades button");
  if (gradeBtn) {
    selected = +gradeBtn.dataset.i;
    setGrade(selected, +gradeBtn.dataset.g);
    return;
  }

  if (ev.target.id === "delBtn") {
    if (!confirm("Delete " + current + " and its judgments?")) return;
    await api("/judge/api/queries/" + encodeURIComponent(current), { method: "DELETE" });
    current = null;
    candidates = [];
    document.getElementById("panel").innerHTML =
      '<p class="hint">Pick a query on the left.</p>';
    loadQueries();
    return;
  }

  if (ev.target.id === "addBtn") {
    const text = prompt("New query (filter tokens like type:pdf are allowed):");
    if (!text) return;
    try {
      const q = await api("/judge/api/queries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text }),
      });
      await loadQueries();
      openQuery(q.qid);
    } catch (e) { alert(e.message); }
    return;
  }

  if (ev.target.id === "benchClose") { document.getElementById("bench").close(); return; }

  if (ev.target.id === "benchBtn") {
    const body = document.getElementById("benchBody");
    body.innerHTML = '<p class="hint">Running every model over every graded query...</p>';
    document.getElementById("bench").showModal();
    try {
      const d = await api("/judge/api/benchmark");
      body.innerHTML = "<h3>" + d.graded + " of " + d.total + " queries graded</h3>" +
        "<table><tr><th>model</th>" +
        d.columns.map(function (c) { return "<th>" + esc(c) + "</th>"; }).join("") + "</tr>" +
        d.results.map(function (r) {
          return "<tr><td>" + esc(r.model) + "</td>" +
            d.columns.map(function (c) { return "<td>" + r[c].toFixed(3) + "</td>"; }).join("") +
            "</tr>";
        }).join("") + "</table>";
    } catch (e) {
      body.innerHTML = '<p class="err">' + esc(e.message) + "</p>";
    }
  }
});

addEventListener("keydown", function (e) {
  if (!candidates.length || e.target.tagName === "INPUT") return;
  if (e.key >= "0" && e.key <= "3") {
    setGrade(selected, +e.key);
    if (selected < candidates.length - 1) selected++;
  } else if (e.key === "j" || e.key === "ArrowDown") {
    selected = Math.min(selected + 1, candidates.length - 1);
  } else if (e.key === "k" || e.key === "ArrowUp") {
    selected = Math.max(selected - 1, 0);
  } else {
    return;
  }
  e.preventDefault();
  render();
  const card = document.getElementById("c" + selected);
  if (card) card.scrollIntoView({ block: "nearest" });
});

loadQueries();
</script>
"""
