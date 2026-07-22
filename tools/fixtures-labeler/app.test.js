const assert = require("assert");
const { buildThemeFile } = require("./app.js");

const out = buildThemeFile(
  "everforest", "~/Wallpapers",
  ["#2d353b", "#7fbbb3"],
  { threshold: 12, top_colors: 3, k: 8, max_hues: 4 },
  [
    { name: "a.jpg", label: "do", reason: null },
    { name: "b.jpg", label: "dont", reason: "wrong-hue" },
  ]
);
assert.strictEqual(out.theme, "everforest");
assert.strictEqual(out.source_dir, "~/Wallpapers");
assert.deepStrictEqual(out.params, { threshold: 12, top_colors: 3, k: 8, max_hues: 4 });
assert.strictEqual(out.items.length, 2);
assert.strictEqual(out.items[1].reason, "wrong-hue");
// a `do` row must not carry a reason
assert.strictEqual(out.items[0].reason, null);
console.log("app.js buildThemeFile OK");
