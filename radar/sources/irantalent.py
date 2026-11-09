import time

from ..http import TIMEOUT
from ..text import html_to_text, to_date, today

NAME = "irantalent"
API = "https://api.irantalent.com/api/v1"
SITE = "https://www.irantalent.com"
KEYWORDS = ["wordpress", "وردپرس", "طراح سایت", "طراح وب سایت", "woocommerce", "ووکامرس", "المنتور", "elementor"]
HEAD = {"Origin": SITE, "Referer": SITE + "/", "Accept": "application/json, text/plain, */*", "Accept-Language": "fa"}
WORK = {"remote": "دورکاری", "hybrid": "هیبرید (ترکیبی)", "on_site": "حضوری"}


def _url(p):
    return f"{SITE}/job/{p.get('slug') or 'job'}/{p['id']}"


def search(s):
    found = {}
    for kw in KEYWORDS:
        r = s.post(f"{API}/employer/position/search", json={"keyword": kw}, headers=HEAD, timeout=TIMEOUT)
        r.raise_for_status()
        for p in r.json().get("data") or []:
            key = f"it-{p['id']}"
            if key in found:
                continue
            d = to_date(p.get("lived_at")) or to_date(p.get("created_at"))
            emp = p.get("employer") or {}
            found[key] = {
                "key": key, "source": NAME, "id": str(p["id"]),
                "title": p.get("title_farsi") or p.get("title") or "",
                "company": emp.get("name_farsi") or emp.get("title_farsi") or emp.get("name") or emp.get("title") or "",
                "age_days": (today() - d).days if d else 0, "posted": d.isoformat() if d else None,
                "url": _url(p),
            }
        time.sleep(0.4)
    return list(found.values())


def _salary(d):
    if not d.get("is_show_salary"):
        return "توافقی"
    lo, hi = d.get("salary_from"), d.get("salary_to")

    def m(v):
        return f"{int(v) // 10_000_000:,}".replace(",", "٬")

    if lo and hi:
        return f"{m(lo)} تا {m(hi)} میلیون تومان"
    if lo:
        return f"از {m(lo)} میلیون تومان"
    return "توافقی"


def detail(s, stub):
    r = s.get(f"{API}/employer/position/{stub['id']}", headers=HEAD, timeout=TIMEOUT)
    r.raise_for_status()
    j = r.json()
    d = j.get("data") if isinstance(j.get("data"), dict) else j
    fa = d.get("language") == "fa"
    role = d.get("role_description_farsi") or d.get("role_description") if fa else d.get("role_description") or d.get("role_description_farsi")
    req = d.get("requirements_description_farsi") or d.get("requirements_description") if fa else d.get("requirements_description") or d.get("requirements_description_farsi")
    desc = html_to_text(role)
    if req and html_to_text(req) not in desc:
        desc += "\n\n📌 شرایط احراز\n" + html_to_text(req)
    emp = d.get("employer") or {}
    loc = d.get("location_text_farsi") or d.get("location_text") or ((d.get("location") or {}).get("title_farsi")) or ""
    et = d.get("employment_type") or {}
    wt = d.get("work_type") or ""
    skills = []
    for k in ("skills", "required_skills", "position_skills"):
        for x in d.get(k) or []:
            if isinstance(x, dict):
                skills.append(x.get("title_farsi") or x.get("title") or x.get("name") or "")
            elif isinstance(x, str):
                skills.append(x)
    exp = d.get("minimum_experience")
    posted = to_date(d.get("lived_at")) or to_date(stub.get("posted"))
    return {
        **stub,
        "title": d.get("title_farsi") or d.get("title") or stub["title"],
        "company": "محرمانه" if d.get("is_anonymous") else (emp.get("name_farsi") or emp.get("title_farsi") or emp.get("name") or stub["company"]),
        "location": loc,
        "work_type": " · ".join(x for x in [(et.get("title_farsi") or et.get("title") or "") if isinstance(et, dict) else "", WORK.get(wt, "")] if x),
        "remote": wt == "remote",
        "salary": _salary(d),
        "experience": f"{exp} سال" if isinstance(exp, (int, float)) and exp else "",
        "skills": [x for x in dict.fromkeys(skills) if x],
        "description": desc,
        "posted": posted.isoformat() if posted else stub.get("posted"),
        "apply_url": stub["url"],
        "expired": bool(d.get("expired_at")),
        "external": bool(d.get("redirection_url") or d.get("is_crawler")),
        "screening": bool(d.get("has_screening_questions")),
    }
