// Quiz logic: run with `node --test tests/js/`.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { isoWeek, pickTest, grade, rating, readShare, shareParams, randomSeed, rng, quotesFound } from "../../site/assets/core.js";

const items = JSON.parse(readFileSync(new URL("../../data/items.json", import.meta.url)));

test("isoWeek", () => {
  assert.equal(isoWeek(new Date("2026-10-25T12:00:00Z")), "2026-W43");
  assert.equal(isoWeek(new Date("2026-10-26T00:30:00Z")), "2026-W44");
  assert.equal(isoWeek(new Date("2027-01-01T12:00:00Z")), "2026-W53");
  assert.equal(isoWeek(new Date("2026-01-01T12:00:00Z")), "2026-W01");
});

test("the same seed gives the same test", () => {
  const a = pickTest(items, { seed: "w-2026-W43" }).map((i) => i.id);
  const b = pickTest(items, { seed: "w-2026-W43" }).map((i) => i.id);
  const c = pickTest(items, { seed: "w-2026-W44" }).map((i) => i.id);
  assert.deepEqual(a, b);
  assert.notDeepEqual(a, c);
});

test("a test has 10 messages, 6 scams, varied types", () => {
  for (let n = 0; n < 200; n++) {
    const t = pickTest(items, { seed: "s" + n });
    assert.equal(t.length, 10);
    assert.equal(t.filter((i) => i.verdict === "scam").length, 6);
    assert.equal(new Set(t.map((i) => i.id)).size, 10);
    const scamTypes = t.filter((i) => i.verdict === "scam").map((i) => i.type);
    assert.equal(new Set(scamTypes).size, 6, "one scam per type");
  }
});

test("featured types come first", () => {
  const featured = ["jury-duty", "utility", "romance"];
  for (let n = 0; n < 50; n++) {
    const types = new Set(pickTest(items, { seed: "f" + n, featured }).filter((i) => i.verdict === "scam").map((i) => i.type));
    for (const f of featured) assert.ok(types.has(f), `${f} in test ${n}`);
  }
});

test("lesson mini test uses one type", () => {
  const t = pickTest(items, { seed: "x", type: "toll-text", size: 5 });
  assert.ok(t.length >= 2);
  assert.ok(t.every((i) => i.type === "toll-text"));
});

test("small banks degrade gracefully", () => {
  const few = items.filter((i) => i.type === "toll-text" || i.type === "romance");
  const t = pickTest(few, { seed: "y" });
  assert.equal(t.length, few.length);
});

test("grade and rating", () => {
  const [s1, s2, l1] = [items.find((i) => i.verdict === "scam"), items.filter((i) => i.verdict === "scam")[1], items.find((i) => i.verdict === "legit")];
  const g = grade([{ item: s1, choice: "scam" }, { item: s2, choice: "legit" }, { item: l1, choice: "scam" }]);
  assert.equal(g.score, 1);
  assert.equal(g.total, 3);
  assert.deepEqual(g.fooledBy, [s2.id]);
  assert.deepEqual(g.missed, [s2.id, l1.id]);
  assert.equal(rating(10, 10).label, "Scam-proof this week");
  assert.equal(rating(8, 10).label, "Sharp eye");
  assert.equal(rating(6, 10).label, "Good instincts");
  assert.equal(rating(2, 10).label, "Worth a second look");
});

test("share links round-trip and reject junk", () => {
  const q = shareParams({ seed: "w-2026-W43", score: 8, total: 10 });
  assert.deepEqual(readShare("?" + q + "&from=friend"), { seed: "w-2026-W43", score: 8, total: 10, from: "friend" });
  assert.deepEqual(readShare("?t=<script>&s=11-10&from=evil"), { seed: null, score: null, total: null, from: null });
  assert.deepEqual(readShare("?s=3-0"), { seed: null, score: null, total: null, from: null });
  assert.deepEqual(readShare(""), { seed: null, score: null, total: null, from: null });
  assert.match(randomSeed(rng("z")), /^[a-z2-9]{6}$/);
});

test("every flag quote is in the message", () => {
  for (const i of items) assert.ok(quotesFound(i), i.id);
});
