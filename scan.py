import argparse
import os
import sys
import time
import traceback
from datetime import datetime, timedelta

from radar import apply, store
from radar.http import session
from radar.relevance import is_relevant, quick_reject
from radar.sources import LABELS, SOURCES
from radar.telegram import Telegram, TelegramError
from radar.text import TEH, to_date, today


def log(*a):
    print(*a, flush=True)


def collect(mode, seen, max_age):
    s = session()
    found, status = [], {}
    for name, src in SOURCES.items():
        info = {"ok": False, "listed": 0, "checked": 0, "relevant": 0, "error": None}
        if not getattr(src, "ENABLED", True):
            info.update(skipped=True, error=getattr(src, "DISABLED_NOTE", "disabled"))
            status[name] = info
            log(f"[{name}] skipped")
            continue
        try:
            stubs = src.search(s)
            info["listed"] = len(stubs)
            for st in stubs:
                if st["age_days"] > max_age:
                    if mode == "scan":
                        seen.setdefault(st["key"], today().isoformat())
                    continue
                if mode == "scan" and st["key"] in seen:
                    continue
                if quick_reject(st["title"]):
                    seen[st["key"]] = today().isoformat()
                    continue
                try:
                    job = src.detail(s, st)
                except Exception as e:
                    log(f"  ! {st['key']} detail failed: {e}")
                    continue
                info["checked"] += 1
                if job.get("expired"):
                    seen[st["key"]] = today().isoformat()
                elif is_relevant(job):
                    found.append(job)
                    info["relevant"] += 1
                else:
                    seen[st["key"]] = today().isoformat()
                time.sleep(0.3)
            info["ok"] = True
        except Exception as e:
            info["error"] = f"{type(e).__name__}: {str(e)[:200]}"
            traceback.print_exc()
        status[name] = info
        log(f"[{name}] {info}")
    return found, status


def sort_key(job):
    d = to_date(job.get("posted")) or today()
    return (d, {"jobvision": 0, "irantalent": 1, "jobinja": 2}.get(job["source"], 3))


def choose(mode, found, jobs, count, first_run):
    uniq = {}
    for j in found:
        uniq.setdefault(j["key"], j)
    found = sorted(uniq.values(), key=sort_key, reverse=True)
    if mode == "test":
        todays = [j for j in found if to_date(j.get("posted")) == today()]
        rest = [j for j in found if j not in todays]
        return sorted((todays + rest)[:count], key=sort_key)
    recent = {j["fp"] for j in jobs if (to_date(j.get("sent_at")) or today()) >= today() - timedelta(days=14)}
    picked, fps = [], set()
    for j in found:
        fp = store.fingerprint(j)
        if fp in recent or fp in fps:
            j["_dup"] = True
            continue
        fps.add(fp)
        picked.append(j)
    return sorted(picked[: (15 if first_run else 30)], key=sort_key)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="scan", choices=["scan", "test", "dry"])
    ap.add_argument("--count", default="5")
    a = ap.parse_args()
    mode = a.mode
    count = max(1, min(20, int(a.count) if str(a.count).isdigit() else 5))

    token, chat = os.getenv("TELEGRAM_BOT_TOKEN", "").strip(), os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if mode != "dry" and not (token and chat):
        log("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID secrets are missing.")
        sys.exit(1)

    seen = store.load("seen.json", {})
    jobs = store.load("jobs.json", [])
    first_run = not seen and mode == "scan"
    max_age = 3 if mode in ("test", "dry") else (2 if first_run else 7)
    log(f"mode={mode} first_run={first_run} max_age={max_age} seen={len(seen)}")

    found, status = collect(mode, seen, max_age)
    chosen = choose(mode, found, jobs, count, first_run)
    for j in found:
        if j.get("_dup"):
            seen[j["key"]] = today().isoformat()

    tg = Telegram(token, chat) if mode != "dry" else None
    sent, errors = 0, []
    for job in chosen:
        auto = apply.available(job)
        if mode == "dry":
            log(f"  → [{LABELS[job['source']]}] {job['title']} | {job.get('company')} | {job.get('posted')} | auto={auto}")
            continue
        try:
            mid = tg.send_job(job, auto)
        except TelegramError as e:
            errors.append(str(e))
            log(f"  ! send failed {job['key']}: {e}")
            if "chat not found" in str(e).lower() or "unauthorized" in str(e).lower() or "rights" in str(e).lower():
                break
            continue
        sent += 1
        seen[job["key"]] = today().isoformat()
        jobs = [x for x in jobs if x["key"] != job["key"]]
        rec = store.record(job, mid, auto)
        rec["sent_at"] = datetime.now(TEH).isoformat(timespec="minutes")
        jobs.insert(0, rec)
        time.sleep(3)

    if mode == "dry":
        log(f"dry run: {len(found)} relevant, {len(chosen)} would be sent")
        return

    store.save("seen.json", store.prune_seen(seen))
    store.save("jobs.json", jobs[:300])
    store.save("status.json", {
        "last_run": datetime.now(TEH).isoformat(timespec="seconds"),
        "mode": mode,
        "sources": status,
        "relevant": len(found),
        "sent": sent,
        "errors": errors[:5],
        "auto_apply": {"jobinja": bool(os.getenv("JOBINJA_COOKIE")) and os.getenv("JOBINJA_ENABLED") == "1",
                       "irantalent": bool(os.getenv("IRANTALENT_TOKEN"))},
    })
    log(f"done: relevant={len(found)} chosen={len(chosen)} sent={sent}")
    if errors and not sent:
        sys.exit(1)


if __name__ == "__main__":
    main()
