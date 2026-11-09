import time

from ..http import TIMEOUT
from ..text import html_to_text, to_date, today

NAME = "jobvision"
API = "https://candidateapi.jobvision.ir/api/v1"
SITE = "https://jobvision.ir"
KEYWORDS = ["wordpress", "وردپرس", "طراح سایت", "طراح وب سایت", "ووکامرس", "woocommerce", "المنتور", "elementor"]
HEAD = {"Origin": SITE, "Referer": SITE + "/", "Accept": "application/json, text/plain, */*"}


def search(s):
    found = {}
    for kw in KEYWORDS:
        body = {"pageSize": 30, "requestedPage": 1, "keyword": kw, "sortBy": 0, "searchId": None}
        r = s.post(f"{API}/JobPost/List", json=body, headers=HEAD, timeout=TIMEOUT)
        r.raise_for_status()
        for p in ((r.json().get("data") or {}).get("jobPosts") or []):
            key = f"jv-{p['id']}"
            if key in found:
                continue
            act = p.get("activationTime") or {}
            d = to_date(act.get("date"))
            age = act.get("passedDays")
            if age is None:
                age = (today() - d).days if d else 0
            found[key] = {
                "key": key, "source": NAME, "id": str(p["id"]), "title": p.get("title") or "",
                "company": ((p.get("company") or {}).get("nameFa") or (p.get("company") or {}).get("nameEn") or ""),
                "age_days": int(age), "posted": d.isoformat() if d else None,
                "url": f"{SITE}/jobs/{p['id']}",
            }
        time.sleep(0.4)
    return list(found.values())


def _loc(loc):
    loc = loc or {}
    prov = (loc.get("province") or {}).get("titleFa") or ""
    city = (loc.get("city") or {}).get("titleFa") or ""
    if city and prov and city != prov:
        return f"{prov}، {city}"
    return city or prov


def detail(s, stub):
    r = s.get(f"{API}/JobPost/Detail", params={"jobPostId": stub["id"]}, headers=HEAD, timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json().get("data") or {}
    skills = [((x.get("software") or {}).get("titleEn") or (x.get("software") or {}).get("titleFa") or "")
              for x in d.get("softwareRequirements") or []]
    skills += [(x.get("titleFa") or x.get("title") or "") if isinstance(x, dict) else str(x) for x in d.get("skills") or []]
    salary = (d.get("salary") or {}).get("titleFa") or "توافقی"
    exp = d.get("requiredRelatedExperienceYears")
    desc = html_to_text(d.get("description"))
    if d.get("workDays"):
        desc += f"\n\n🕘 روز و ساعت کاری: {d['workDays']}"
    act = to_date((d.get("activationTime") or {}).get("date")) or to_date(stub.get("posted"))
    return {
        **stub,
        "title": d.get("title") or stub["title"],
        "company": ((d.get("company") or {}).get("nameFa") or stub["company"]),
        "location": _loc(d.get("location")),
        "work_type": (d.get("workType") or {}).get("titleFa") or "",
        "remote": bool(d.get("isRemote")),
        "salary": salary,
        "experience": f"{exp} سال" if exp else "",
        "skills": [x for x in dict.fromkeys(skills) if x],
        "description": desc,
        "posted": act.isoformat() if act else stub.get("posted"),
        "apply_url": stub["url"],
        "expired": bool(d.get("isExpired")),
        "external": bool(d.get("linkOutAddress")),
    }
