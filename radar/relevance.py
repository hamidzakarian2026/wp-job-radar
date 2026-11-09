import re

from .text import norm

STRONG = re.compile(
    r"word ?press|ورد ?پرس|woo ?commerce|وو ?کامرس|elementor|المنتور|wp ?bakery|gutenberg|گوتنبرگ"
    r"|\bdivi\b|دیوی|crocoblock|jet ?engine|\bwp\b"
)
DESIGN_TITLE = re.compile(
    r"طراح(?:ی)? (?:و \S+ )?(?:و \S+ )?(?:وب ?سایت|سایت|وب\b)"
    r"|web ?site design|web design|site design|webmaster|وب ?مستر"
)
WEBISH_TITLE = re.compile(
    r"سایت|\bوب\b|web|site|php|front ?-?end|فرانت|full ?-?stack|فول ?استک|برنامه ?نویس|توسعه ?دهنده"
    r"|developer|programmer|ادمین|admin|\bcms\b|فروشگاه (?:اینترنتی|آنلاین)|e-?commerce|پشتیبان فنی|کارشناس فنی"
)
NEG_TITLE = re.compile(
    r"گرافیک|graphic|motion|موشن|عکاس|photo|ویدیو|ویدئو|video|تدوین|محتوا|content|سئو|\bseo\b|marketing"
    r"|مارکتینگ|بازاریابی|فروش(?!گاه)|sales|حسابدار|account|\bui\b|\bux\b|کپی ?رایت|copywrit|social|سوشال"
    r"|اینستاگرام|instagram|پشتیبانی مشتری|call center|اپراتور|منشی|کارآموز فروش"
)


def is_strong(job):
    return bool(STRONG.search(norm(job.get("title"))) or STRONG.search(norm(job.get("description"))) or
                STRONG.search(norm(" ".join(job.get("skills") or []))))


def quick_reject(title):
    t = norm(title)
    if STRONG.search(t) or DESIGN_TITLE.search(t):
        return False
    return bool(NEG_TITLE.search(t)) or not WEBISH_TITLE.search(t)


def is_relevant(job):
    title = norm(job.get("title"))
    if STRONG.search(title) or DESIGN_TITLE.search(title):
        return True
    body = norm(" ".join([job.get("description") or "", " ".join(job.get("skills") or [])]))
    return bool(STRONG.search(body) and WEBISH_TITLE.search(title) and not NEG_TITLE.search(title))
