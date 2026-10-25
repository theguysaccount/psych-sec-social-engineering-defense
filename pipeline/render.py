"""Render quiz messages to HTML at build time, exactly as site/assets/core.js does in the browser.

tests/js/render.test.mjs runs both renderers over every item and requires identical output.
Run directly to print {item id: html} for all items as JSON.
"""
import html
import json
import re
import sys
from pathlib import Path

CHANNELS = {
    "sms": ("Text message", "💬"),
    "email": ("Email", "✉️"),
    "call": ("Phone call", "📞"),
    "voicemail": ("Voicemail", "📞"),
    "dm": ("Chat message", "💬"),
    "popup": ("Pop-up", "⚠️"),
    "letter": ("Paper mail", "📬"),
    "sign": ("Printed sign", "🪧"),
    "ad": ("Social media ad", "📣"),
    "app": ("App notification", "📱"),
    "video": ("Video call", "🎥"),
}
THREAD = {"sms", "dm"}
DIALOGUE = {"call", "voicemail", "video"}
OPEN, CLOSE = "\u0001", "\u0002"
SPEAKER = re.compile(r"^([A-Z][A-Za-z .'’-]{0,30}): ")


def escape(s):
    # Same five characters as escapeHtml in core.js.
    return html.escape(str(s), quote=True).replace("&#x27;", "&#39;")


def render_inline(text, quotes=()):
    s = str(text or "")
    for n, q in enumerate(quotes):
        if not q:
            continue
        i = s.find(q)
        if i >= 0:
            s = s[:i] + OPEN + str(n + 1) + OPEN + q + CLOSE + s[i + len(q):]
    s = escape(s)
    s = re.sub(r"\[\[(.+?)\]\]", r'<span class="fakelink" title="Links are disabled in this test">\1</span>', s)
    s = re.sub(r"\{\{(.+?)\}\}", r'<span class="fakebtn">\1</span>', s)
    s = s.replace("[QR code]", '<span class="qr" role="img" aria-label="QR code"></span>')
    s = re.sub(r"\[([^\[\]]+)\]", r"<i>[\1]</i>", s)
    s = re.sub("\u0001(\\d+)\u0001", r'<mark class="tell" data-n="\1">', s)
    return s.replace(CLOSE, "</mark>").replace("\n", "<br>")


def render_body(text, quotes, channel):
    out = []
    for para in re.split(r"\n{2,}", str(text or "")):
        if channel in THREAD:
            mine = para.startswith("You: ")
            out.append('<div class="bubble%s">%s</div>' % (" out" if mine else "", render_inline(para[5:] if mine else para, quotes)))
            continue
        if channel in DIALOGUE:
            m = SPEAKER.match(para)
            if m:
                out.append('<p class="line"><span class="who">%s:</span> %s</p>' % (escape(m.group(1)), render_inline(para[m.end():], quotes)))
                continue
        out.append("<p>%s</p>" % render_inline(para, quotes))
    return "".join(out)


def render_message(item):
    label, icon = CHANNELS.get(item["channel"], (item["channel"], ""))
    quotes = [f.get("quote") or "" for f in item.get("flags", [])]
    head = '<div class="msg-top"><span aria-hidden="true">%s</span> <b>%s</b>' % (icon, label)
    fields = ""
    if item["channel"] == "email":
        fields = '<div class="msg-fields"><div><span>From</span> %s</div>' % render_inline(item.get("from"), quotes)
        if item.get("subject"):
            fields += "<div><span>Subject</span> %s</div>" % render_inline(item["subject"], quotes)
        fields += "</div>"
    elif item.get("from"):
        head += " · " + render_inline(item["from"], quotes)
    head += "</div>"
    return '<div class="msg %s" data-item="%s">%s%s<div class="msg-body">%s</div></div>' % (
        item["channel"], escape(item["id"]), head, fields, render_body(item["body"], quotes, item["channel"]))


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    items = json.loads((root / "data" / "items.json").read_text(encoding="utf-8"))
    json.dump({i["id"]: render_message(i) for i in items}, sys.stdout, ensure_ascii=False)
