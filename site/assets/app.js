// The test UI. Logic lives in core.js; this file only touches the DOM.
import { pickTest, grade, rating, readShare, shareParams, randomSeed, isoWeek, renderMessage, escapeHtml, CHANNELS } from "./core.js";

const cfgEl = document.getElementById("site-config");
const CFG = cfgEl ? JSON.parse(cfgEl.textContent) : { root: "./", siteUrl: location.origin };
const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Analytics are off unless the site was built with GOATCOUNTER_URL (see OPERATIONS.md).
function track(name, detail) {
  try {
    if (window.goatcounter && window.goatcounter.count) {
      window.goatcounter.count({ path: `event/${name}${detail ? "/" + detail : ""}`, title: name, event: true });
    }
  } catch (e) { /* never let analytics break the test */ }
}

let dataPromise = null;
function loadData() {
  if (!dataPromise) {
    const week = fetch(CFG.root + "data/week.json").then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
    const bank = fetch(CFG.root + "data/bank.json").then((r) => {
      if (!r.ok) throw new Error("bank " + r.status);
      return r.json();
    });
    dataPromise = Promise.all([bank, week]).then(([b, w]) => ({ items: b.items, types: b.types, week: w || {} }));
  }
  return dataPromise;
}

const share = readShare(location.search);

function lessonUrl(types, slug) {
  return CFG.root + "scams/" + slug + "/";
}

function shareRow(url, text, subject, where) {
  const enc = encodeURIComponent;
  const body = `${text} ${url}`;
  return `<div class="btn-row">
    ${navigator.share ? `<button class="btn small" type="button" data-share="${where}">Share…</button>` : ""}
    <a class="btn small secondary" href="sms:?&body=${enc(body)}" data-track="${where}-sms">Text it</a>
    <a class="btn small secondary" href="mailto:?subject=${enc(subject)}&body=${enc(text + "\n\n" + url)}" data-track="${where}-email">Email it</a>
    <a class="btn small secondary" href="https://wa.me/?text=${enc(body)}" target="_blank" rel="noopener" data-track="${where}-whatsapp">WhatsApp</a>
    <button class="btn small secondary" type="button" data-copy="${escapeHtml(url)}">Copy link</button>
  </div>`;
}

function wireShare(el, payloads) {
  el.querySelectorAll("[data-share]").forEach((b) => b.addEventListener("click", async () => {
    const p = payloads[b.dataset.share];
    track("share", b.dataset.share + "-native");
    try { await navigator.share({ title: p.subject, text: p.text, url: p.url }); } catch (e) { /* cancelled */ }
  }));
  el.querySelectorAll("[data-copy]").forEach((b) => b.addEventListener("click", async () => {
    track("share", "copy");
    try {
      await navigator.clipboard.writeText(b.dataset.copy);
      b.insertAdjacentHTML("afterend", '<span class="copied" role="status">Copied</span>');
    } catch (e) {
      window.prompt("Copy this link:", b.dataset.copy);
    }
  }));
  el.querySelectorAll("[data-track]").forEach((a) => a.addEventListener("click", () => track("share", a.dataset.track)));
}

class Quiz {
  constructor(el) {
    this.el = el;
    this.mode = el.dataset.mode || "weekly"; // weekly | type | embed
    this.type = el.dataset.type || null;
    this.intro = el.querySelector("[data-intro]");
    this.stage = el.querySelector("[data-stage]");
    el.querySelectorAll("[data-start]").forEach((b) => b.addEventListener("click", () => this.start()));
    if (this.mode === "embed") this.start();
  }

  async start(seed) {
    let data;
    try {
      data = await loadData();
    } catch (e) {
      this.stage.hidden = false;
      this.stage.innerHTML = '<p class="callout">The test couldn\'t load. Check your connection and reload the page.</p>';
      return;
    }
    this.data = data;
    if (this.mode === "type") {
      this.seed = seed || randomSeed();
      this.items = pickTest(data.items, { seed: this.seed, type: this.type, size: 5 });
    } else {
      this.weekly = !seed && (this.mode === "embed" || !share.seed || share.seed === `w-${isoWeek()}`);
      this.seed = seed || share.seed || `w-${isoWeek()}`;
      this.items = pickTest(data.items, { seed: this.seed, featured: data.week.featured || [] });
      if (this.mode === "embed") {
        // The weekly card shows a scam from one of this week's featured types when there is one.
        const featured = data.week.featured || [];
        this.items = [this.items.find((i) => i.verdict === "scam" && featured.includes(i.type)) || this.items[0]];
      }
    }
    this.answers = [];
    this.i = 0;
    if (this.intro) this.intro.hidden = true;
    this.stage.hidden = false;
    track(this.mode === "type" ? "lesson_test_start" : this.mode === "embed" ? "embed_start" : "test_start");
    this.renderQuestion();
  }

  scrollTop() {
    if (this.mode === "embed") return;
    const top = this.stage.getBoundingClientRect().top + window.scrollY - 12;
    if (window.scrollY > top || top - window.scrollY > window.innerHeight * 0.5) {
      window.scrollTo({ top, behavior: reduceMotion ? "auto" : "smooth" });
    }
  }

  get current() { return this.items[this.i]; }

  renderQuestion() {
    const item = this.current;
    const n = this.items.length;
    const right = this.answers.filter((a) => a.choice === a.item.verdict).length;
    this.stage.innerHTML = `
      ${n > 1 ? `<div class="qhead"><span>Message ${this.i + 1} of ${n}</span><span>${this.i ? `${right} right so far` : ""}</span></div>
      <div class="progress" aria-hidden="true"><span style="width:${(this.i / n) * 100}%"></span></div>` : ""}
      ${item.context ? `<p class="context">${escapeHtml(item.context)}</p>` : ""}
      ${renderMessage(item)}
      <p class="ask" id="ask-${this.i}">Scam or legit?</p>
      <div class="answer-row" role="group" aria-labelledby="ask-${this.i}">
        <button class="btn scam" type="button" data-choice="scam">Scam</button>
        <button class="btn legit" type="button" data-choice="legit">Legit</button>
      </div>
      <div data-feedback aria-live="polite"></div>`;
    this.stage.querySelectorAll("[data-choice]").forEach((b) => b.addEventListener("click", () => this.answer(b.dataset.choice)));
    if (this.i > 0) this.scrollTop();
  }

  answer(choice) {
    const item = this.current;
    if (this.answers.length > this.i) return;
    this.answers.push({ item, choice });
    const ok = choice === item.verdict;
    this.stage.querySelectorAll("[data-choice]").forEach((b) => {
      b.disabled = true;
      b.setAttribute("aria-pressed", String(b.dataset.choice === choice));
    });
    this.stage.querySelector(".msg").classList.add("revealed");
    const type = this.data.types[item.type] || { name: item.type };
    const last = this.i === this.items.length - 1;
    const scam = item.verdict === "scam";
    const nextLabel = this.mode === "embed" ? "" : last ? "See my score →" : "Next message →";
    const fb = this.stage.querySelector("[data-feedback]");
    fb.innerHTML = `
      <div class="feedback ${ok ? "right" : "wrong"}" data-result="${ok ? "right" : "wrong"}">
        <h3>${ok ? "✓ Right." : "✗ Not this time."} It's <span class="verdict-tag ${item.verdict}">${scam ? "a scam" : "legit"}</span></h3>
        <p>${escapeHtml(item.why)}</p>
        <p><b>${scam ? "The tells (highlighted above):" : "Why it's fine:"}</b></p>
        <ol>${item.flags.map((f) => `<li>${escapeHtml(f.text)}</li>`).join("")}</ol>
        <p class="safe">Safe move: ${escapeHtml(item.do)}</p>
        <div class="btn-row">
          ${nextLabel ? `<button class="btn" type="button" data-next>${nextLabel}</button>` : ""}
          ${this.mode === "type" ? "" : `<a class="btn secondary small" href="${lessonUrl(this.data.types, item.type)}" target="_blank" rel="noopener">2-minute lesson: ${escapeHtml(type.name)}</a>`}
        </div>
        ${this.mode === "embed" ? `<p><a class="btn" href="${CFG.siteUrl}/" target="_blank" rel="noopener" data-track="embed-cta">Take the full 2-minute test →</a></p>` : ""}
      </div>`;
    const next = fb.querySelector("[data-next]");
    if (next) {
      next.addEventListener("click", () => this.next());
      next.focus({ preventScroll: true });
    }
    fb.querySelectorAll("[data-track]").forEach((a) => a.addEventListener("click", () => track("click", a.dataset.track)));
    if (this.mode === "embed") track("embed_answer", ok ? "right" : "wrong");
  }

  next() {
    if (this.i < this.items.length - 1) {
      this.i++;
      this.renderQuestion();
    } else {
      this.renderResults();
    }
  }

  renderResults() {
    const g = grade(this.answers);
    const r = rating(g.score, g.total);
    const types = this.data.types;
    const byId = Object.fromEntries(this.items.map((i) => [i.id, i]));
    const fooled = g.fooledBy.map((id) => byId[id]);
    const overcautious = g.missed.filter((id) => byId[id].verdict === "legit").map((id) => byId[id]);
    const channel = (it) => (CHANNELS[it.channel] ? CHANNELS[it.channel].label : it.channel);
    const typeName = (it) => (types[it.type] ? types[it.type].name : it.type);
    const li = (it) => it.verdict === "scam"
      ? `<li><b>${escapeHtml(typeName(it))}</b> (${escapeHtml(channel(it).toLowerCase())}): ${escapeHtml(it.why)} <a href="${lessonUrl(types, it.type)}">Lesson →</a></li>`
      : `<li><b>A real ${escapeHtml(channel(it).toLowerCase())}</b>: ${escapeHtml(it.why)} <a href="${lessonUrl(types, it.type)}">How to tell it from ${escapeHtml(typeName(it).toLowerCase())} →</a></li>`;

    let html;
    if (this.mode === "type") {
      const t = types[this.type];
      const pageUrl = `${CFG.siteUrl}/scams/${this.type}/`;
      const payloads = { page: { url: pageUrl, text: `Have you seen this scam? “${t.name}”: how it works and how to spot it.`, subject: `Watch out for this scam: ${t.name}` } };
      html = `
        <p class="score">${g.score} of ${g.total}</p>
        <p class="rating">${g.score === g.total ? "You'd spot this one." : "Now you know what to look for."}</p>
        ${fooled.length ? `<p>The one${fooled.length > 1 ? "s" : ""} that got past you: ${fooled.map((i) => escapeHtml(i.why)).join(" ")}</p>` : ""}
        <div class="btn-row"><a class="btn" href="${CFG.root}">Take the full 10-message test</a><button class="btn secondary" type="button" data-again>Try these again</button></div>
        <div class="share-box"><h3>Know someone who'd fall for this?</h3><p>Send them this page. It takes two minutes to read.</p>${shareRow(pageUrl, payloads.page.text, payloads.page.subject, "page")}</div>`;
      this.stage.innerHTML = html;
      wireShare(this.stage, payloads);
      track("lesson_test_complete", `${g.score}-${g.total}`);
    } else {
      const base = `${CFG.siteUrl}/`;
      const parentsUrl = `${base}?t=${encodeURIComponent(this.seed)}&from=parents`;
      const friendUrl = `${base}?${shareParams({ seed: this.seed, score: g.score, total: g.total })}&from=friend`;
      const payloads = {
        parents: { url: parentsUrl, text: "I just took this 2-minute test on spotting scam texts, emails and calls. Scammers are using AI now, so they're harder to spot. Worth a try:", subject: "A 2-minute scam test worth taking" },
        friend: { url: friendUrl, text: `I spotted ${g.score} out of ${g.total} on the Spot the Scam test. Can you beat me?`, subject: `Can you beat my ${g.score}/${g.total} on the Spot the Scam test?` },
      };
      html = `
        <p class="note">${this.weekly ? "This week's test" : "Practice test"}</p>
        <p class="score" data-score="${g.score}">${g.score} out of ${g.total}</p>
        <p class="rating">${escapeHtml(r.label)}</p>
        <p>${escapeHtml(r.blurb)}</p>
        ${share.score !== null && share.seed === this.seed ? `<p class="banner">Your friend scored ${share.score} out of ${share.total}. ${g.score > share.score ? "You beat them." : g.score === share.score ? "It's a tie." : "They win this round."}</p>` : ""}
        ${fooled.length ? `<h2>Scams that got past you</h2><ul class="missed">${fooled.map(li).join("")}</ul>` : ""}
        ${overcautious.length ? `<h2>Real messages you called scams</h2><p>Being suspicious is a good instinct. Here's what made these safe:</p><ul class="missed">${overcautious.map(li).join("")}</ul>` : ""}
        <div class="share-box">
          <h3>Send this test to your parents</h3>
          <p>Scam calls and texts now sound like real people. Two minutes of practice helps anyone spot them.</p>
          ${shareRow(parentsUrl, payloads.parents.text, payloads.parents.subject, "parents")}
        </div>
        <div class="share-box">
          <h3>Challenge a friend</h3>
          <p>They get the same ${g.total} messages, and see your score when they finish.</p>
          ${shareRow(friendUrl, payloads.friend.text, payloads.friend.subject, "friend")}
        </div>
        ${CFG.teamUrl ? `<div class="callout"><b>Training a team?</b> Run this test with your staff and see where they slip. <a href="${escapeHtml(CFG.teamUrl)}" rel="noopener" data-track="team">Get the team version →</a></div>` : ""}
        <div class="btn-row">
          <button class="btn secondary" type="button" data-again>Take another test</button>
          <a class="btn secondary" href="${CFG.root}how-to-spot-a-scam/">The 4 signs of any scam</a>
        </div>`;
      this.stage.innerHTML = html;
      wireShare(this.stage, payloads);
      this.stage.querySelectorAll("[data-track]").forEach((a) => a.addEventListener("click", () => track("click", a.dataset.track)));
      track("test_complete", `${g.score}-${g.total}`);
    }
    const again = this.stage.querySelector("[data-again]");
    if (again) again.addEventListener("click", () => this.start(randomSeed()));
    this.result = g;
    this.scrollTop();
  }
}

function showArrivalBanner() {
  const el = document.getElementById("share-banner");
  if (!el) return;
  let msg = "";
  if (share.score !== null) {
    msg = `A friend scored ${share.score} out of ${share.total} on this test. You'll get the same messages. Can you beat them?`;
  } else if (share.from === "parents") {
    msg = "Someone who cares about you sent you this. It takes about two minutes, and nothing you do here is saved or sent anywhere.";
  }
  if (msg) {
    el.textContent = msg;
    el.hidden = false;
  }
}

// Share buttons rendered into the page at build time.
function wireStatic() {
  document.querySelectorAll("[data-share-native]").forEach((b) => {
    if (!navigator.share) return;
    b.hidden = false;
    b.addEventListener("click", async () => {
      track("share", "page-native");
      try { await navigator.share({ title: b.dataset.title, text: b.dataset.text, url: b.dataset.url }); } catch (e) { /* cancelled */ }
    });
  });
  document.querySelectorAll("[data-copy]").forEach((b) => b.addEventListener("click", async () => {
    track("share", "page-copy");
    try {
      await navigator.clipboard.writeText(b.dataset.copy);
      b.insertAdjacentHTML("afterend", '<span class="copied" role="status">Copied</span>');
    } catch (e) {
      window.prompt("Copy this link:", b.dataset.copy);
    }
  }));
}

showArrivalBanner();
wireStatic();
const quizzes = [...document.querySelectorAll("[data-quiz]")].map((el) => new Quiz(el));
if (quizzes.length) loadData().catch(() => {}); // warm the cache so Start is instant

const demoParam = new URLSearchParams(location.search).get("demo");
if (demoParam !== null) {
  import("./selftest.js").then((m) => m.demo(quizzes[0], demoParam));
}
if (/[?&]selftest=1\b/.test(location.search)) {
  import("./selftest.js").then((m) => m.run(quizzes[0])).catch((e) => {
    document.body.dataset.selftest = "fail: " + e.message;
  });
}
