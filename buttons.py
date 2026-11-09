import os
import sys
from datetime import datetime

from radar import apply, store
from radar.telegram import Telegram, TelegramError, keyboard
from radar.text import TEH, esc


def main():
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN", "").strip(), os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token:
        print("no bot token")
        return
    tg = Telegram(token, chat)
    updates = tg.call("getUpdates", timeout=0, allowed_updates=["callback_query"])
    if not updates:
        print("no updates")
        return

    jobs = {j["key"]: j for j in store.load("jobs.json", [])}
    applied = store.load("applied.json", {})
    admins, done_now, changed = {}, set(), False

    for u in updates:
        cq = u.get("callback_query")
        if not cq:
            continue
        data = cq.get("data") or ""
        uid = (cq.get("from") or {}).get("id")
        msg = cq.get("message") or {}
        mchat = (msg.get("chat") or {}).get("id") or chat

        def answer(text):
            try:
                tg.call("answerCallbackQuery", callback_query_id=cq["id"], text=text[:190], show_alert=False)
            except TelegramError:
                pass

        if data == "done":
            answer("رزومه قبلاً ارسال شده ✅")
            continue
        if not data.startswith("ap|"):
            continue
        key = data[3:]
        if uid not in admins:
            admins[uid] = tg.is_admin(uid, mchat)
        if not admins[uid]:
            answer("فقط ادمین کانال می‌تواند رزومه بفرستد")
            continue
        job = jobs.get(key)
        if not job:
            answer("اطلاعات این آگهی پیدا نشد")
            continue
        mid = msg.get("message_id") or job.get("message_id")
        if key in done_now or (applied.get(key) or {}).get("ok"):
            answer("رزومه قبلاً ارسال شده ✅")
            if mid:
                try:
                    tg.call("editMessageReplyMarkup", chat_id=mchat, message_id=mid, reply_markup=keyboard(job, True, "done"))
                except TelegramError:
                    pass
            continue

        try:
            result = apply.apply(job)
            ok, note = True, result
        except apply.ApplyError as e:
            ok, note = False, str(e)
        except Exception as e:
            ok, note = False, f"خطای غیرمنتظره: {type(e).__name__}: {str(e)[:150]}"
        print(key, ok, note)

        applied[key] = {"ok": ok, "note": note, "at": datetime.now(TEH).isoformat(timespec="minutes")}
        changed = True
        if ok:
            done_now.add(key)
        answer(("✅ " if ok else "⚠️ ") + note)
        if mid:
            try:
                tg.call("editMessageReplyMarkup", chat_id=mchat, message_id=mid,
                        reply_markup=keyboard(job, True, "done" if ok else "failed"))
            except TelegramError as e:
                print("edit failed:", e)
            if not ok:
                try:
                    tg.call("sendMessage", chat_id=mchat, text=f"⚠️ <b>ارسال رزومه ناموفق بود</b>\n{esc(note)}",
                            parse_mode="HTML", reply_parameters={"message_id": mid, "allow_sending_without_reply": True},
                            disable_notification=True)
                except TelegramError:
                    pass

    tg.call("getUpdates", offset=updates[-1]["update_id"] + 1, timeout=0, allowed_updates=["callback_query"])
    if changed:
        store.save("applied.json", applied)


if __name__ == "__main__":
    try:
        main()
    except TelegramError as e:
        print("telegram error:", e)
        sys.exit(1)
