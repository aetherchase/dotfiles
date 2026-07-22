"use strict";

// Pure: assemble the theme file object from UI state. Reason is kept only for `dont`.
function buildThemeFile(theme, sourceDir, palette, params, rows) {
  return {
    theme,
    source_dir: sourceDir,
    palette,
    params,
    items: rows.map((r) => ({
      name: r.name,
      label: r.label,
      reason: r.label === "dont" ? (r.reason || "other") : null,
    })),
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { buildThemeFile };
}

// ---- Browser glue (skipped under node) ----
if (typeof document !== "undefined") {
  const THEMES = window.FIXTURE_THEMES || {};
  const rows = []; // {name, label, reason, el}
  const $ = (id) => document.getElementById(id);

  function fillThemes() {
    const sel = $("theme");
    Object.keys(THEMES).sort().forEach((slug) => {
      const o = document.createElement("option");
      o.value = o.textContent = slug;
      sel.appendChild(o);
    });
    sel.addEventListener("change", showHints);
    showHints();
  }

  function showHints() {
    const t = THEMES[$("theme").value] || { palette: [], backgrounds: [] };
    $("palette").innerHTML = t.palette
      .map((h) => `<span class="sw" style="background:${h}" title="${h}"></span>`)
      .join("");
    $("bgs").innerHTML = t.backgrounds
      .map((p) => `<img class="bg" src="file://${p}" alt="">`)
      .join("");
  }

  function addFiles(fileList) {
    for (const file of fileList) {
      const row = { name: file.name, label: "dont", reason: "wrong-hue" };
      const el = document.createElement("div");
      el.className = "row";
      const url = URL.createObjectURL(file);
      el.innerHTML =
        `<img class="thumb" src="${url}">` +
        `<span class="nm">${file.name}</span>` +
        `<select class="lab"><option value="do">do</option>` +
        `<option value="dont" selected>dont</option></select>` +
        `<select class="rsn">` +
        ["wrong-hue", "polychrome", "neutral", "other"]
          .map((r) => `<option value="${r}">${r}</option>`)
          .join("") +
        `</select>`;
      const lab = el.querySelector(".lab");
      const rsn = el.querySelector(".rsn");
      lab.addEventListener("change", () => {
        row.label = lab.value;
        rsn.disabled = lab.value === "do";
      });
      rsn.addEventListener("change", () => (row.reason = rsn.value));
      row.el = el;
      rows.push(row);
      $("rows").appendChild(el);
    }
  }

  function currentParams() {
    return {
      threshold: parseFloat($("threshold").value),
      top_colors: parseInt($("top_colors").value, 10),
      k: parseInt($("k").value, 10),
      max_hues: parseInt($("max_hues").value, 10),
    };
  }

  function exportFile() {
    const theme = $("theme").value;
    const data = buildThemeFile(
      theme, $("source_dir").value, (THEMES[theme] || {}).palette || [],
      currentParams(), rows
    );
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = theme + ".json";
    a.click();
  }

  function importFile(file) {
    const reader = new FileReader();
    reader.onload = () => {
      const d = JSON.parse(reader.result);
      $("theme").value = d.theme;
      $("source_dir").value = d.source_dir;
      $("threshold").value = d.params.threshold;
      $("top_colors").value = d.params.top_colors;
      $("k").value = d.params.k;
      $("max_hues").value = d.params.max_hues;
      showHints();
      $("rows").innerHTML = "";
      rows.length = 0;
      // Prefill label/reason rows (previews reappear when the user re-adds the images).
      d.items.forEach((it) => {
        const el = document.createElement("div");
        el.className = "row";
        el.innerHTML = `<span class="nm">${it.name}</span> — ${it.label}` +
          (it.reason ? ` (${it.reason})` : "") + " <em>re-add file for preview</em>";
        $("rows").appendChild(el);
        rows.push({ name: it.name, label: it.label, reason: it.reason, el });
      });
    };
    reader.readAsText(file);
  }

  window.addEventListener("DOMContentLoaded", () => {
    fillThemes();
    $("files").addEventListener("change", (e) => addFiles(e.target.files));
    $("export").addEventListener("click", exportFile);
    $("import").addEventListener("change", (e) => e.target.files[0] && importFile(e.target.files[0]));
    const dz = $("drop");
    dz.addEventListener("dragover", (e) => e.preventDefault());
    dz.addEventListener("drop", (e) => {
      e.preventDefault();
      addFiles(e.dataTransfer.files);
    });
  });
}
