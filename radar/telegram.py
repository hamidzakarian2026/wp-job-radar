import html
import re
import time

import requests

from .relevance import STRONG
from .sources import LABELS, TAGS
from .text import esc, jalali_label, norm, relative_label, to_date

LIMIT = 4096


class TelegramError(Exception):
    pass


class Telegram:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id

    def call(self, method, **params):
        for attempt in range(5):
            try:
                r = requests.post(f"https://api.telegram.org/bot{self.token}/{method}", json=params, timeout=30)
            except requests.RequestException as e:
                if attempt == 4:
                    raise TelegramError(str(e).replace(self.token, "***"))
                time.sleep(3)
                continue
            j = r.json() if r.content else {}
            if j.get("ok"):
                return j["result"]
            if r.status_code == 429:
                time.sleep(int((j.get("parameters") or {}).get("retry_after", 5)) + 1)
                continue
            raise TelegramError(j.get("description") or f"HTTP {r.status_code}")
        raise TelegramError("too many retries")

    def send_job(self, job, auto_apply):
        text = render(job)
        markup = keyboard(job, auto_apply)
        try:
            msg = self.call("sendMessage", chat_id=self.chat_id, text=text, parse_mode="HTML",
                            reply_markup=markup, link_preview_options={"is_disabled": True})
        except TelegramError as e:
            if "parse" not in str(e).lower() and "entit" not in str(e).lower():
                raise
            plain = re.sub(r"<[^>]+>", "", html.unescape(text))[:LIMIT]
            msg = self.call("sendMessage", chat_id=self.chat_id, text=plain, reply_markup=markup,
                            link_preview_options={"is_disabled": True})
        return msg["message_id"]

    def is_admin(self, user_id, chat_id=None):
        try:
            m = self.call("getChatMember", chat_id=chat_id or self.chat_id, user_id=user_id)
            return m.get("status") in ("creator", "administrator")
        except TelegramError:
            return False


def apply_button(job, auto):
    if auto:
        return {"text": "📨 ارسال رزومه", "callback_data": f"ap|{job['key']}"}
    return {"text": "📨 ارسال رزومه در سایت", "url": job.get("apply_url") or job["url"]}


def view_button(job):
    return {"text": f"🔗 مشاهده در {LABELS[job['source']]}", "url": job["url"]}


def keyboard(job, auto, state=None):
    if state == "done":
        first = {"text": "✅ رزومه ارسال شد", "callback_data": "done"}
    elif state == "failed":
        first = {"text": "⚠️ ارسال نشد · تلاش مجدد", "callback_data": f"ap|{job['key']}"}
    else:
        first = apply_button(job, auto)
    return {"inline_keyboard": [[first, view_button(job)]]}


def _u16(s):
    return len(s.encode("utf-16-le")) // 2


def _visible(s):
    return _u16(html.unescape(re.sub(r"<[^>]+>", "", s)))


def render(job):
    title = re.sub(r"^\s*استخدام\s+", "", job.get("title") or "").strip()
    lines = [f"💼 <b>{esc(title)}</b>", ""]
    if job.get("company"):
        lines.append(f"🏢 {esc(job['company'])}")
    loc = job.get("location") or ""
    if job.get("remote") and "دورکاری" not in loc:
        loc = f"{loc} · 🏠 دورکاری" if loc else "🏠 دورکاری"
    if loc:
        lines.append(f"📍 {esc(loc)}")
    if job.get("work_type"):
        lines.append(f"🕒 {esc(job['work_type'])}")
    if job.get("salary"):
        lines.append(f"💰 {esc(job['salary'])}")
    if job.get("experience"):
        lines.append(f"🎯 سابقه: {esc(job['experience'])}")
    if job.get("skills"):
        lines.append(f"🧩 {esc(' · '.join(job['skills'][:8]))}")
    d = to_date(job.get("posted"))
    when = " · ".join(x for x in [relative_label(d), jalali_label(d)] if x)
    lines.append(f"🗓 {esc(when)} · 🌐 {LABELS[job['source']]}")
    header = "\n".join(lines)

    topic = "#وردپرس" if STRONG.search(norm(f"{job.get('title')} {job.get('description')}")) else "#طراحی_سایت"
    tags = " ".join([TAGS[job["source"]], topic] + (["#دورکاری"] if job.get("remote") else []))

    desc = (job.get("description") or "").strip() or "—"
    budget = LIMIT - _visible(header) - _u16(tags) - 60
    if _u16(desc) > budget:
        n, used = 0, 0
        for ch in desc:
            used += 2 if ord(ch) > 0xFFFF else 1
            if used > budget:
                break
            n += 1
        cut = desc[:n]
        cut = cut[: cut.rfind("\n")] if cut.rfind("\n") > n * 0.7 else cut
        desc = cut.rstrip() + "\n…\n(ادامه‌ی متن در سایت)"
    return f"{header}\n\n<blockquote expandable><b>📄 متن کامل آگهی</b>\n{esc(desc)}</blockquote>\n{tags}"
