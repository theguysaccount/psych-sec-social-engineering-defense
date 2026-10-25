// Quiz logic shared by the browser (app.js) and the Node tests. No DOM access in this file.

export const TEST_SIZE = 10;
export const SCAMS_PER_TEST = 6;

// ISO-8601 week key, e.g. "2026-W43". Everyone gets the same weekly test in the same week.
export function isoWeek(date = new Date()) {
  const d = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const day = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((d - yearStart) / 86400000 + 1) / 7);
  return `${d.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

// FNV-1a, 32-bit.
export function hashString(s) {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

// mulberry32: small, fast, deterministic.
export function rng(seed) {
  let a = typeof seed === "number" ? seed >>> 0 : hashString(String(seed));
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function shuffle(list, rand) {
  const a = list.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// Choose a test from the bank.
// - The same seed and bank always give the same test, so a shared link replays it.
// - Scam types that recent FTC alerts are about (`featured`) come first.
// - At most `perType` items of one type, so a test covers many tricks.
// - `type` restricts the test to one scam type (the mini test on each lesson page).
export function pickTest(items, { seed, size = TEST_SIZE, scams = SCAMS_PER_TEST, featured = [], type = null, perType = 1 } = {}) {
  const rand = rng(seed);
  if (type) {
    return shuffle(items.filter((i) => i.type === type), rand).slice(0, size);
  }
  const pool = shuffle(items, rand);
  const scamPool = pool.filter((i) => i.verdict === "scam");
  const legitPool = pool.filter((i) => i.verdict === "legit");
  const rank = (t) => (featured.includes(t) ? featured.indexOf(t) : featured.length);
  scamPool.sort((a, b) => rank(a.type) - rank(b.type)); // stable: shuffled order kept within a rank

  const chosen = [];
  const perTypeCount = {};
  const take = (cands, n) => {
    for (let limit = perType; n > 0 && limit <= size; limit++) {
      for (const it of cands) {
        if (n <= 0) break;
        if (chosen.includes(it) || (perTypeCount[it.type] || 0) >= limit) continue;
        chosen.push(it);
        perTypeCount[it.type] = (perTypeCount[it.type] || 0) + 1;
        n--;
      }
    }
  };
  const nScam = Math.min(scams, scamPool.length);
  take(scamPool, nScam);
  take(legitPool, Math.min(size - nScam, legitPool.length));
  return shuffle(chosen, rand);
}

export function grade(answers) {
  const right = answers.filter((a) => a.choice === a.item.verdict);
  const missed = answers.filter((a) => a.choice !== a.item.verdict);
  const missedTypes = [];
  for (const a of missed) if (!missedTypes.includes(a.item.type)) missedTypes.push(a.item.type);
  return {
    score: right.length,
    total: answers.length,
    missed: missed.map((a) => a.item.id),
    missedTypes,
    // Saying "legit" to a scam is the costly mistake; flag it separately.
    fooledBy: missed.filter((a) => a.item.verdict === "scam").map((a) => a.item.id),
  };
}

export function rating(score, total) {
  const r = total ? score / total : 0;
  if (r === 1) return { label: "Scam-proof this week", blurb: "You caught every trick. Send it to someone who'd want to know these exist." };
  if (r >= 0.8) return { label: "Sharp eye", blurb: "You spotted most of them. The ones you missed are the ones scammers count on." };
  if (r >= 0.6) return { label: "Good instincts", blurb: "A few got past you. The short lessons below cover exactly those tricks." };
  return { label: "Worth a second look", blurb: "These are built to fool people, and AI makes them look polished. Two minutes with the lessons below changes that." };
}

// Share links carry the test seed and the score only. Nothing else, and nothing is stored anywhere.
const SEED_RE = /^[A-Za-z0-9-]{1,24}$/;

export function shareParams({ seed, score, total }) {
  const p = new URLSearchParams();
  if (seed) p.set("t", seed);
  if (Number.isInteger(score) && Number.isInteger(total)) p.set("s", `${score}-${total}`);
  return p.toString();
}

export function readShare(search) {
  const p = new URLSearchParams(search || "");
  const out = { seed: null, score: null, total: null, from: null };
  const t = p.get("t");
  if (t && SEED_RE.test(t)) out.seed = t;
  const m = /^(\d{1,2})-(\d{1,2})$/.exec(p.get("s") || "");
  if (m) {
    const score = Number(m[1]);
    const total = Number(m[2]);
    if (total > 0 && total <= 20 && score <= total) {
      out.score = score;
      out.total = total;
    }
  }
  const from = p.get("from");
  if (from === "parents" || from === "friend") out.from = from;
  return out;
}

export function randomSeed(rand = Math.random) {
  let s = "";
  for (let i = 0; i < 6; i++) s += "abcdefghjkmnpqrstuvwxyz23456789"[Math.floor(rand() * 31)];
  return s;
}

// Message markup used in the item bank:
//   [[example.com/path]]  a link, rendered as text that can't be clicked
//   {{Verify now}}        a button, rendered as a dead button
//   [QR code]             a QR code graphic
//   [stage direction]     shown in italics
//   "You: ..."            (texts and chats) a message you sent
//   "Caller: ..."         (calls) a speaker label
// Every flag may quote a phrase of the message. Quotes are wrapped in <mark class="tell"> and
// stay invisible until the answer is revealed. pipeline/render.py mirrors this exactly; the tests
// compare the two on every item.
export const CHANNELS = {
  sms: { label: "Text message", icon: "💬" },
  email: { label: "Email", icon: "✉️" },
  call: { label: "Phone call", icon: "📞" },
  voicemail: { label: "Voicemail", icon: "📞" },
  dm: { label: "Chat message", icon: "💬" },
  popup: { label: "Pop-up", icon: "⚠️" },
  letter: { label: "Paper mail", icon: "📬" },
  sign: { label: "Printed sign", icon: "🪧" },
  ad: { label: "Social media ad", icon: "📣" },
  app: { label: "App notification", icon: "📱" },
  video: { label: "Video call", icon: "🎥" },
};
const THREAD = new Set(["sms", "dm"]);
const DIALOGUE = new Set(["call", "voicemail", "video"]);

export function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

const OPEN = "\u0001";
const CLOSE = "\u0002";

export function renderInline(text, quotes = []) {
  let s = String(text || "");
  quotes.forEach((q, n) => {
    if (!q) return;
    const i = s.indexOf(q);
    if (i >= 0) s = s.slice(0, i) + OPEN + (n + 1) + OPEN + q + CLOSE + s.slice(i + q.length);
  });
  return escapeHtml(s)
    .replace(/\[\[(.+?)\]\]/g, '<span class="fakelink" title="Links are disabled in this test">$1</span>')
    .replace(/\{\{(.+?)\}\}/g, '<span class="fakebtn">$1</span>')
    .replace(/\[QR code\]/g, '<span class="qr" role="img" aria-label="QR code"></span>')
    .replace(/\[([^\[\]]+)\]/g, "<i>[$1]</i>")
    .replace(/\u0001(\d+)\u0001/g, '<mark class="tell" data-n="$1">')
    .replace(/\u0002/g, "</mark>")
    .replace(/\n/g, "<br>");
}

export function renderBody(text, quotes, channel) {
  return String(text || "")
    .split(/\n{2,}/)
    .map((para) => {
      if (THREAD.has(channel)) {
        const out = para.startsWith("You: ");
        return `<div class="bubble${out ? " out" : ""}">${renderInline(out ? para.slice(5) : para, quotes)}</div>`;
      }
      if (DIALOGUE.has(channel)) {
        const m = /^([A-Z][A-Za-z .'’-]{0,30}): /.exec(para);
        if (m) return `<p class="line"><span class="who">${escapeHtml(m[1])}:</span> ${renderInline(para.slice(m[0].length), quotes)}</p>`;
      }
      return `<p>${renderInline(para, quotes)}</p>`;
    })
    .join("");
}

export function renderMessage(item) {
  const ch = CHANNELS[item.channel] || { label: item.channel, icon: "" };
  const quotes = (item.flags || []).map((f) => f.quote || "");
  let head = `<div class="msg-top"><span aria-hidden="true">${ch.icon}</span> <b>${ch.label}</b>`;
  let fields = "";
  if (item.channel === "email") {
    fields = `<div class="msg-fields"><div><span>From</span> ${renderInline(item.from, quotes)}</div>` +
      (item.subject ? `<div><span>Subject</span> ${renderInline(item.subject, quotes)}</div>` : "") + "</div>";
  } else if (item.from) {
    head += ` · ${renderInline(item.from, quotes)}`;
  }
  head += "</div>";
  return `<div class="msg ${item.channel}" data-item="${escapeHtml(item.id)}">${head}${fields}<div class="msg-body">${renderBody(item.body, quotes, item.channel)}</div></div>`;
}

// Does every flag quote appear in the message, within one paragraph? Used by the tests and the build.
export function quotesFound(item) {
  const parts = [item.from, item.subject, ...String(item.body || "").split(/\n{2,}/)].filter(Boolean);
  return (item.flags || []).filter((f) => f.quote).every((f) => parts.some((p) => p.includes(f.quote)));
}
