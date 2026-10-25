// The build (Python) and the browser (JS) must render every message identically.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { renderMessage } from "../../site/assets/core.js";

const root = new URL("../../", import.meta.url);
const items = JSON.parse(readFileSync(new URL("data/items.json", root)));
const py = JSON.parse(execFileSync("python3", ["pipeline/render.py"], { cwd: root, encoding: "utf8" }));

test("python and js renderers agree", () => {
  assert.equal(Object.keys(py).length, items.length);
  for (const item of items) assert.equal(renderMessage(item), py[item.id], item.id);
});

test("rendered messages have no live links and mark every quote", () => {
  for (const item of items) {
    const html = renderMessage(item);
    assert.doesNotMatch(html, /<a\s/i, item.id);
    assert.doesNotMatch(html, /<script/i, item.id);
    const quotes = item.flags.filter((f) => f.quote).length;
    const marks = (html.match(/<mark class="tell"/g) || []).length;
    assert.ok(marks >= quotes, `${item.id}: ${marks} marks for ${quotes} quotes`);
  }
});
