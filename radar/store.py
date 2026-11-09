import json
import os
from datetime import timedelta

from .text import norm, to_date, today

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def load(name, default):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(name, value):
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, name)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=1)
    os.replace(path + ".tmp", path)


def fingerprint(job):
    t = norm(job.get("title")).replace("استخدام", "").strip()
    return f"{t}|{norm(job.get('company'))[:24]}"


def prune_seen(seen, days=120):
    limit = today() - timedelta(days=days)
    return {k: v for k, v in seen.items() if (to_date(v) or today()) >= limit}


def record(job, message_id, auto):
    keep = ("key", "source", "id", "title", "company", "location", "work_type", "remote", "salary",
            "experience", "skills", "posted", "url", "apply_url", "company_slug", "screening", "external")
    rec = {k: job.get(k) for k in keep if job.get(k) not in (None, "", [])}
    rec["summary"] = (job.get("description") or "")[:400]
    rec["fp"] = fingerprint(job)
    rec["message_id"] = message_id
    rec["apply_mode"] = "auto" if auto else "link"
    rec["sent_at"] = today().isoformat()
    return rec
