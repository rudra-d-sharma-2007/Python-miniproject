// dupescan — runs the repo's Python module in the browser via Pyodide.
// The algorithm lives in duplicate_detector.py; this file is only the shell.

import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";

const INDEX_URL = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";
const MAX_RENDER_CHIPS = 400;

const state = { pyodide: null, ready: false };

const els = {
  status: document.getElementById("status"),
  badge: document.getElementById("runtimeBadge"),
  badgeText: document.getElementById("runtimeBadgeText"),
  input: document.getElementById("input"),
  asNumbers: document.getElementById("asNumbers"),
  showCounts: document.getElementById("showCounts"),
  detectBtn: document.getElementById("detectBtn"),
  sampleBtn: document.getElementById("sampleBtn"),
  fileInput: document.getElementById("fileInput"),
  results: document.getElementById("results"),
  reportMeta: document.getElementById("reportMeta"),
  stats: document.getElementById("stats"),
  phaseSort: document.getElementById("phaseSort"),
  phaseScan: document.getElementById("phaseScan"),
  dupList: document.getElementById("dupList"),
  sortedChips: document.getElementById("sortedChips"),
  sortedMeta: document.getElementById("sortedMeta"),
};

function setStatus(text, kind) {
  els.status.textContent = text;
  els.status.dataset.kind = kind;
  els.badge.dataset.kind = kind;
  els.badgeText.textContent =
    kind === "ok" ? "python online" : kind === "err" ? "runtime error" : "booting…";
}

function lastLine(err) {
  const text = String((err && err.message) || err).trim();
  const lines = text.split("\n");
  return lines[lines.length - 1] || text;
}

async function boot() {
  try {
    setStatus("Loading the Python runtime (first visit may take a moment)…", "busy");
    state.pyodide = await loadPyodide({ indexURL: INDEX_URL });

    setStatus("Fetching duplicate_detector.py…", "busy");
    const response = await fetch("./duplicate_detector.py");
    if (!response.ok) {
      throw new Error(`could not fetch duplicate_detector.py (HTTP ${response.status})`);
    }
    const code = await response.text();
    state.pyodide.FS.writeFile("duplicate_detector.py", code);
    await state.pyodide.runPythonAsync("import duplicate_detector");

    const version = state.pyodide.runPython(
      "import sys; sys.version.split()[0]"
    );
    state.ready = true;
    els.detectBtn.disabled = false;
    setStatus(`Ready — CPython ${version} running locally in WebAssembly.`, "ok");
  } catch (err) {
    setStatus(
      `Python failed to start: ${lastLine(err)}. ` +
        "Check your connection (the runtime loads from a CDN), then reload.",
      "err"
    );
  }
}

function runDetect() {
  if (!state.ready) return;

  const text = els.input.value;
  if (!text.trim()) {
    els.results.hidden = true;
    setStatus("Waiting for input — paste some values or load the sample.", "busy");
    return;
  }

  state.pyodide.globals.set("web_text", text);
  state.pyodide.globals.set("web_as_number", els.asNumbers.checked);

  try {
    const t0 = performance.now();
    const jsonStr = state.pyodide.runPython(
      "import json\n" +
        "json.dumps(duplicate_detector.analyze_text(web_text, as_number=web_as_number))"
    );
    const wallMs = performance.now() - t0;
    render(JSON.parse(jsonStr), wallMs);
    setStatus(
      `Done — Python sorted and scanned in ${wallMs.toFixed(1)} ms (whole round trip).`,
      "ok"
    );
  } catch (err) {
    els.results.hidden = true;
    setStatus(`Python reported: ${lastLine(err)}`, "err");
  }
}

function statCard(label, value, className) {
  const card = document.createElement("div");
  card.className = "stat" + (className ? ` ${className}` : "");
  const labelEl = document.createElement("span");
  labelEl.className = "label";
  labelEl.textContent = label;
  const valueEl = document.createElement("span");
  valueEl.className = "value";
  valueEl.textContent = value;
  card.append(labelEl, valueEl);
  return card;
}

function render(report, wallMs) {
  els.results.hidden = false;
  els.reportMeta.textContent = `${report.total_items} items · ${wallMs.toFixed(1)} ms end to end`;

  const found = report.duplicate_count > 0;

  els.stats.replaceChildren(
    statCard("Total items", String(report.total_items)),
    statCard("Unique values", String(report.unique_count)),
    statCard(
      "Duplicated values",
      String(report.duplicate_count),
      found ? "hot" : "clean"
    ),
    statCard("Extra copies", String(report.duplicate_items), found ? "hot" : "clean"),
    statCard("Merge sort", `${report.sort_ms.toFixed(2)} ms`),
    statCard("Scan", `${report.scan_ms.toFixed(2)} ms`)
  );

  const sortMs = report.sort_ms;
  const scanMs = report.scan_ms;
  const total = Math.max(sortMs + scanMs, 0.001);
  els.phaseSort.style.width = `${(sortMs / total) * 100}%`;
  els.phaseScan.style.width = `${(scanMs / total) * 100}%`;

  els.dupList.replaceChildren();
  if (!found) {
    const note = document.createElement("div");
    note.className = "clean-note";
    note.textContent = "✓ No duplicates — every value appears exactly once.";
    els.dupList.append(note);
  } else {
    const showCounts = els.showCounts.checked;
    report.duplicates.forEach((dup, i) => {
      const item = document.createElement("span");
      item.className = "dup-item";
      item.style.animationDelay = `${Math.min(i, 20) * 18}ms`;
      const value = document.createElement("span");
      value.textContent = String(dup.value);
      item.append(value);
      if (showCounts) {
        const count = document.createElement("span");
        count.className = "count";
        count.textContent = `×${dup.occurrences}`;
        item.append(count);
      }
      els.dupList.append(item);
    });
  }

  const dupValues = new Set(report.duplicates.map((d) => String(d.value)));
  const sorted = report.sorted.map(String);
  const shown = sorted.slice(0, MAX_RENDER_CHIPS);
  els.sortedChips.replaceChildren();
  shown.forEach((value, i) => {
    const chip = document.createElement("span");
    chip.className = "chip" + (dupValues.has(value) ? " is-dup" : "");
    chip.style.animationDelay = `${Math.min(i, 24) * 12}ms`;
    chip.textContent = value;
    els.sortedChips.append(chip);
  });
  if (sorted.length > shown.length) {
    const more = document.createElement("span");
    more.className = "chips-more";
    more.textContent = `… +${sorted.length - shown.length} more (all scanned)`;
    els.sortedChips.append(more);
  }
  els.sortedMeta.textContent = `(${sorted.length} values, duplicates highlighted)`;

  els.results.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function loadSample() {
  const words = [
    "ember", "quartz", "basalt", "cobalt", "ivory",
    "onyx", "saffron", "topaz", "willow", "zephyr",
  ];
  const tokens = [];
  for (let i = 0; i < 42; i++) {
    tokens.push(words[Math.floor(Math.random() * words.length)]);
  }
  for (let i = 0; i < 24; i++) {
    tokens.push(String(100 + Math.floor(Math.random() * 60) * 7));
  }
  // Shuffle so the sorted output is visibly the algorithm's work.
  for (let i = tokens.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [tokens[i], tokens[j]] = [tokens[j], tokens[i]];
  }
  els.input.value = tokens.join(" ");
  setStatus("Sample loaded — press “detect duplicates”.", "busy");
}

els.detectBtn.addEventListener("click", runDetect);
els.sampleBtn.addEventListener("click", loadSample);
els.showCounts.addEventListener("change", () => {
  if (!els.results.hidden) runDetect();
});

els.fileInput.addEventListener("change", async () => {
  const file = els.fileInput.files && els.fileInput.files[0];
  if (!file) return;
  try {
    els.input.value = await file.text();
    setStatus(`Loaded ${file.name} (${els.input.value.length.toLocaleString()} chars).`, "busy");
  } catch (err) {
    setStatus(`Could not read file: ${lastLine(err)}`, "err");
  }
  els.fileInput.value = "";
});

els.input.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    event.preventDefault();
    runDetect();
  }
});

boot();
