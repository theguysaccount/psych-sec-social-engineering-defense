// End-to-end self-test, loaded only with ?selftest=1. It plays the test through the real UI:
// one deliberately wrong answer, then right answers, and checks the score, feedback and share links.
// The result lands in <body data-selftest="pass|fail: reason"> and a <pre id="selftest"> element,
// which scripts/e2e.sh reads from headless Chrome.
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function until(fn, what, ms = 8000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    const v = fn();
    if (v) return v;
    await wait(25);
  }
  throw new Error("timed out waiting for " + what);
}

export async function run(quiz) {
  const log = [];
  const finish = (status) => {
    document.body.dataset.selftest = status;
    const pre = document.createElement("pre");
    pre.id = "selftest";
    pre.textContent = status + "\n" + log.join("\n");
    document.body.appendChild(pre);
  };
  try {
    if (!quiz) throw new Error("no quiz on this page");
    if (quiz.mode !== "embed") {
      const start = await until(() => quiz.el.querySelector("[data-start]"), "start button");
      start.click();
    }
    await until(() => quiz.items && quiz.stage.querySelector("[data-choice]"), "first message");
    const total = quiz.items.length;
    if (quiz.mode === "weekly" && total !== 10) throw new Error(`expected 10 messages, got ${total}`);
    const scams = quiz.items.filter((i) => i.verdict === "scam").length;
    log.push(`messages=${total} scams=${scams} seed=${quiz.seed}`);
    for (let i = 0; i < total; i++) {
      const item = quiz.current;
      const wrong = i === 0 && total > 1;
      const choice = wrong ? (item.verdict === "scam" ? "legit" : "scam") : item.verdict;
      quiz.stage.querySelector(`[data-choice="${choice}"]`).click();
      const fb = await until(() => quiz.stage.querySelector("[data-result]"), "feedback");
      const expect = wrong ? "wrong" : "right";
      if (fb.dataset.result !== expect) throw new Error(`message ${i + 1}: feedback ${fb.dataset.result}, expected ${expect}`);
      if (!quiz.stage.querySelector(".msg.revealed")) throw new Error(`message ${i + 1}: tells not revealed`);
      const marks = quiz.stage.querySelectorAll(".msg mark.tell").length;
      const quotes = item.flags.filter((f) => f.quote).length;
      if (marks < quotes) throw new Error(`message ${i + 1} (${item.id}): ${marks} highlights for ${quotes} quotes`);
      log.push(`${i + 1}. ${item.id} ${choice} -> ${fb.dataset.result} (${marks} highlights)`);
      const next = quiz.stage.querySelector("[data-next]");
      if (next) next.click();
    }
    if (quiz.mode === "embed") return finish("pass");
    const score = await until(() => quiz.stage.querySelector(".score"), "score");
    const expected = total > 1 ? `${total - 1} ` : `${total} `;
    if (!score.textContent.startsWith(expected)) throw new Error(`score "${score.textContent}", expected to start with "${expected}"`);
    if (quiz.mode === "weekly") {
      const copy = [...quiz.stage.querySelectorAll("[data-copy]")].map((b) => b.dataset.copy);
      if (copy.length !== 2) throw new Error("expected 2 share links, got " + copy.length);
      if (!copy[1].includes(`s=${total - 1}-${total}`)) throw new Error("friend link lacks the score: " + copy[1]);
      if (!copy.every((u) => u.includes("t=" + encodeURIComponent(quiz.seed)))) throw new Error("share links lack the test seed");
      log.push("share: " + copy.join(" | "));
    }
    log.push("score: " + score.textContent);
    finish("pass");
  } catch (e) {
    finish("fail: " + e.message);
  }
}

// Screenshot helper: ?demo=N answers N messages correctly and stops (N=0 shows the first message),
// leaving the last feedback on screen; ?demo=end plays to the results.
export async function demo(quiz, n) {
  if (quiz.mode !== "embed") (await until(() => quiz.el.querySelector("[data-start]"), "start button")).click();
  await until(() => quiz.items && quiz.stage.querySelector("[data-choice]"), "first message");
  const total = n === "end" ? quiz.items.length : Math.min(Number(n) || 0, quiz.items.length);
  for (let i = 0; i < total; i++) {
    quiz.stage.querySelector(`[data-choice="${quiz.current.verdict}"]`).click();
    await until(() => quiz.stage.querySelector("[data-result]"), "feedback");
    if (i < total - 1 || n === "end") {
      const next = quiz.stage.querySelector("[data-next]");
      if (next) next.click();
    }
  }
  window.scrollTo(0, 0);
  document.body.dataset.demo = "ready";
}
