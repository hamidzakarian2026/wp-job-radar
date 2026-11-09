import html
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

TEH = ZoneInfo("Asia/Tehran")
FA = "۰۱۲۳۴۵۶۷۸۹"
AR = "٠١٢٣٤٥٦٧٨٩"
MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


def en_digits(s):
    return str(s or "").translate(str.maketrans(FA + AR, "0123456789" * 2))


def fa_digits(s):
    return str(s).translate(str.maketrans("0123456789", FA))


def norm(s):
    s = en_digits(s).lower()
    s = s.replace("ي", "ی").replace("ك", "ک").replace("ة", "ه").replace("ۀ", "ه")
    s = re.sub(r"[‌‍‎‏ ً-ٟ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def esc(s):
    return html.escape(s or "", quote=False)


def html_to_text(h):
    if not h:
        return ""
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", h)
    h = re.sub(r"(?i)<br\s*/?>", "\n", h)
    h = re.sub(r"(?i)<li[^>]*>", "\n• ", h)
    h = re.sub(r"(?i)</(p|div|li|ul|ol|h[1-6]|tr|section|blockquote)>", "\n", h)
    h = re.sub(r"<[^>]+>", "", h)
    t = html.unescape(h).replace("\xa0", " ").replace("\r", "")
    out, blank = [], False
    for line in t.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        if not line:
            if out and not blank:
                out.append("")
                blank = True
            continue
        if out and out[-1] == "•":
            out[-1] = "• " + line.lstrip("•").strip()
        elif out and out[-1] == "" and len(out) > 1 and out[-2] == "•":
            out.pop()
            out[-1] = "• " + line
        else:
            out.append(line)
        blank = False
    out = [x for x in out if x != "•"]
    res = []
    for i, x in enumerate(out):
        if x == "" and res and res[-1].startswith("•") and i + 1 < len(out) and out[i + 1].startswith("•"):
            continue
        res.append(x)
    return "\n".join(res).strip()


def g2j(gy, gm, gd):
    gdm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 + gd + gdm[gm - 1]
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        return jy, 1 + days // 31, 1 + days % 31
    return jy, 7 + (days - 186) // 30, 1 + (days - 186) % 30


def today():
    return datetime.now(TEH).date()


def to_date(v):
    if not v:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        dt = v
    else:
        s = str(v).strip().replace(" ", "T")
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            try:
                return date.fromisoformat(s[:10])
            except ValueError:
                return None
        if len(str(v).strip()) <= 10:
            return dt.date()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TEH)
    return dt.astimezone(TEH).date()


def jalali_label(d):
    if not d:
        return ""
    jy, jm, jd = g2j(d.year, d.month, d.day)
    return f"{fa_digits(jd)} {MONTHS[jm - 1]} {fa_digits(jy)}"


def relative_label(d):
    if not d:
        return ""
    n = (today() - d).days
    if n <= 0:
        return "امروز"
    if n == 1:
        return "دیروز"
    return f"{fa_digits(n)} روز پیش"


def age_from_text(t):
    t = norm(t)
    if "امروز" in t or "ساعت" in t or "دقیقه" in t:
        return 0
    if "دیروز" in t:
        return 1
    if "بیش" in t:
        return 31
    m = re.search(r"(\d+)", t)
    n = int(m.group(1)) if m else 0
    if "هفته" in t:
        return n * 7
    if "ماه" in t:
        return n * 30
    return n
