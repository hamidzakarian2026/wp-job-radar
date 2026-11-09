import json
import os
import re
import time

from bs4 import BeautifulSoup

from ..http import TIMEOUT
from ..text import age_from_text, html_to_text, norm, to_date, today
from datetime import timedelta

NAME = "jobinja"
ENABLED = os.getenv("JOBINJA_ENABLED") == "1"
DISABLED_NOTE = "جابینجا درخواست‌های سرورهای خارج از ایران (گیت‌هاب) را مسدود می‌کند (403)"
SITE = "https://jobinja.ir"
KEYWORDS = ["وردپرس", "wordpress", "طراح سایت", "طراح وب سایت", "ووکامرس", "المنتور"]
URL_RE = re.compile(r"/companies/([^/?#]+)/jobs/([^/?#]+)")


def search(s):
    found = {}
    for kw in KEYWORDS:
        params = {"filters[keywords][0]": kw, "sort_by": "published_at_desc", "page": 1}
        r = s.get(f"{SITE}/jobs", params=params, timeout=TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        for li in soup.select("li.c-jobListView__item"):
            a = li.select_one("a.c-jobListView__titleLink")
            if not a or not a.get("href"):
                continue
            m = URL_RE.search(a["href"])
            if not m:
                continue
            company_slug, code = m.groups()
            key = f"jb-{code}"
            if key in found:
                continue
            metas = [x.get_text(" ", strip=True) for x in li.select(".c-jobListView__metaItem")]
            passed = li.select_one(".c-jobListView__passedDays")
            age = age_from_text(passed.get_text(" ", strip=True)) if passed else 0
            found[key] = {
                "key": key, "source": NAME, "id": code, "title": a.get_text(" ", strip=True),
                "company": (metas[0].split("|")[0].strip() if metas else ""),
                "age_days": age, "posted": (today() - timedelta(days=age)).isoformat(),
                "url": f"{SITE}/companies/{company_slug}/jobs/{code}",
                "company_slug": company_slug,
                "list_meta": metas,
            }
        time.sleep(0.6)
    return list(found.values())


def _ld(soup):
    for sc in soup.select('script[type="application/ld+json"]'):
        try:
            j = json.loads(sc.string or sc.get_text())
        except Exception:
            continue
        for item in (j if isinstance(j, list) else [j]):
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return {}


def _info(soup):
    out = {}
    for li in soup.select(".c-infoBox__item"):
        t = li.select_one(".c-infoBox__itemTitle")
        if not t:
            continue
        vals = [x.get_text(" ", strip=True) for x in li.select(".tags span")] or \
               [li.get_text(" ", strip=True).replace(t.get_text(" ", strip=True), "").strip()]
        out[norm(t.get_text(" ", strip=True))] = [v for v in vals if v]
    return out


def _pick(info, *labels):
    for lb in labels:
        for k, v in info.items():
            if lb in k and v:
                return v
    return []


def detail(s, stub):
    r = s.get(stub["url"], timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    ld = _ld(soup)
    info = _info(soup)
    desc_html = ld.get("description") or str(soup.select_one(".s-jobDesc") or "")
    loc = " ".join(_pick(info, "موقعیت مکانی"))
    loc = "، ".join(dict.fromkeys(p.strip() for p in re.split(r"[،,]", loc) if p.strip()))
    work = " ".join(_pick(info, "نوع همکاری"))
    remote = ld.get("jobLocationType") == "TELECOMMUTE" or "دورکاری" in " ".join(stub.get("list_meta") or []) or "دورکاری" in work
    org = (ld.get("hiringOrganization") or {}).get("name") or stub["company"]
    title = ld.get("title") or stub["title"]
    posted = to_date(ld.get("datePosted")) or to_date(stub.get("posted"))
    return {
        **stub,
        "title": title,
        "company": org.split("|")[0].strip(),
        "location": loc,
        "work_type": work,
        "remote": remote,
        "salary": " ".join(_pick(info, "حقوق")) or "توافقی",
        "experience": " ".join(_pick(info, "سابقه")),
        "skills": _pick(info, "مهارت"),
        "description": html_to_text(desc_html),
        "posted": posted.isoformat() if posted else stub.get("posted"),
        "apply_url": stub["url"],
        "expired": False,
        "external": False,
    }
