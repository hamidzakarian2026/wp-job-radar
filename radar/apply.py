import html
import json
import os
import re
from urllib.parse import unquote

from bs4 import BeautifulSoup

from .http import TIMEOUT, session


class ApplyError(Exception):
    pass


def available(job):
    if job.get("source") == "jobinja":
        return bool(os.getenv("JOBINJA_COOKIE"))
    if job.get("source") == "irantalent":
        return bool(os.getenv("IRANTALENT_TOKEN")) and not job.get("screening") and not job.get("external")
    return False


def _msg(r):
    try:
        j = r.json()
    except ValueError:
        return f"HTTP {r.status_code}"
    parts = [str(j.get("message") or j.get("error") or "")]
    errs = j.get("errors")
    if isinstance(errs, dict):
        parts += [" ".join(map(str, v)) if isinstance(v, list) else str(v) for v in errs.values()]
    return " | ".join(p for p in parts if p)[:300] or f"HTTP {r.status_code}"


def apply_jobinja(job):
    cookie = os.getenv("JOBINJA_COOKIE", "").strip()
    if cookie.lower().startswith("cookie:"):
        cookie = cookie[7:].strip()
    s = session()
    s.headers["Cookie"] = cookie
    url = f"https://jobinja.ir/companies/{job['company_slug']}/jobs/{job['id']}"
    r = s.get(url, timeout=TIMEOUT)
    if r.status_code == 404:
        raise ApplyError("آگهی دیگر در جابینجا فعال نیست")
    r.raise_for_status()
    if re.search(r"isAuthenticated\s*=\s*!!parseInt\('0'\)", r.text):
        raise ApplyError("سشن جابینجا منقضی شده؛ کوکی تازه را در Secret به نام JOBINJA_COOKIE بگذار")
    soup = BeautifulSoup(r.text, "lxml")
    form = soup.find("oc-apply-form")
    if not form or not form.get("init-state"):
        if re.search(r"قبلا?ً?[^<]{0,60}ارسال|رزومه شما[^<]{0,40}ارسال شده", r.text):
            return "قبلاً برای این آگهی رزومه فرستاده‌ای"
        raise ApplyError("فرم ارسال رزومه در صفحه پیدا نشد (شاید آگهی بسته شده)")
    st = json.loads(html.unescape(form["init-state"]))
    if st.get("needs_phone_verification"):
        raise ApplyError("جابینجا تأیید شماره موبایل می‌خواهد؛ یک بار دستی در سایت تأیید کن")
    emp = st.get("employee") or {}
    f = emp.get("file") or {}
    choice = emp.get("latest_choice") or ("apply_choice_uploaded_cv" if f else "apply_choice_jobinja_profile")
    file_id = "" if choice == "apply_choice_jobinja_profile" else (f.get("uuid") or f.get("id") or "")
    meta = soup.find("meta", attrs={"name": "csrf-token"})
    body = {
        "email": emp.get("email", ""), "_ref": st.get("_ref", ""), "full_name": emp.get("full_name", ""),
        "contact_number": emp.get("contact_number", ""), "file_id": file_id, "create_job_alert": 0,
        "verification_token": None,
    }
    api = f"https://jobinja.ir/api/v10/companies/{st.get('company_id') or job['company_slug']}/jobs/{st.get('job_id') or job['id']}/apply"
    r = s.post(api, json=body, timeout=TIMEOUT, headers={
        "X-CSRF-TOKEN": meta["content"] if meta else "", "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json", "Origin": "https://jobinja.ir", "Referer": url,
    })
    if r.status_code in (200, 201):
        return "رزومه از طریق جابینجا ارسال شد"
    if r.status_code in (401, 419):
        raise ApplyError("سشن جابینجا منقضی شده؛ کوکی تازه بگذار")
    raise ApplyError(f"جابینجا: {_msg(r)}")


def _it_token():
    raw = unquote(os.getenv("IRANTALENT_TOKEN", "").strip())
    if raw.startswith("{"):
        try:
            raw = json.loads(raw).get("access_token", "")
        except ValueError:
            pass
    return raw[7:] if raw.lower().startswith("bearer ") else raw


def apply_irantalent(job):
    api = "https://api.irantalent.com/api/v1"
    s = session()
    s.headers.update({"Authorization": f"Bearer {_it_token()}", "Accept": "application/json",
                      "Origin": "https://www.irantalent.com", "Referer": job["url"], "Accept-Language": "fa"})
    r = s.get(f"{api}/candidate/profile", timeout=TIMEOUT)
    if r.status_code == 401:
        raise ApplyError("توکن ایران‌تلنت منقضی شده؛ مقدار تازه را در Secret به نام IRANTALENT_TOKEN بگذار")
    r.raise_for_status()
    prof = r.json()
    prof = prof.get("data") if isinstance(prof.get("data"), dict) else prof
    cv = prof.get("cv") or {}
    cv_id = cv.get("id") if isinstance(cv, dict) else cv
    if not cv_id:
        raise ApplyError("رزومه‌ای در پروفایل ایران‌تلنت پیدا نشد")
    r = s.post(f"{api}/candidate/cv/{cv_id}/position/{job['id']}/apply",
               json={"cover_letter": "", "return_path": job["url"]}, timeout=TIMEOUT)
    if r.status_code in (200, 201, 204):
        return "رزومه از طریق ایران‌تلنت ارسال شد"
    raise ApplyError(f"ایران‌تلنت: {_msg(r)}")


def apply(job):
    if job.get("source") == "jobinja":
        return apply_jobinja(job)
    if job.get("source") == "irantalent":
        if job.get("screening"):
            raise ApplyError("این آگهی سؤال غربالگری دارد؛ باید در سایت جواب بدهی")
        return apply_irantalent(job)
    raise ApplyError("ارسال خودکار برای این سایت فعال نیست")
