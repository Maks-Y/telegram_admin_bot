from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.types import (
    InputMediaPhoto, InputMediaVideo, InputMediaDocument,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from .db import fetchall, fetchone, execute, get_setting
from .config import get_config

cfg = get_config()


def get_channel_id() -> int | None:
    val = get_setting("TARGET_CHANNEL_ID")
    if val:
        return int(val)
    return cfg.target_channel_id

def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Берём все due-слоты в локальном времени и публикуем по очереди."""
    sched = AsyncIOScheduler(timezone=cfg.timezone)

    async def tick():
        rows = fetchall(
            "SELECT id, draft_id, run_at "
            "FROM schedules "
            "WHERE status='pending' "
            "  AND run_at <= strftime('%Y-%m-%d %H:%M:%S','now','localtime') "
            "ORDER BY run_at ASC, id ASC "
            "LIMIT 50"
        )
        for sid, draft_id, _ in rows:
            try:
                execute("UPDATE schedules SET status='running' WHERE id=? AND status='pending'", (sid,))
                ok = await _publish(bot, draft_id, get_channel_id())
                execute("UPDATE schedules SET status=? WHERE id=?", ("done" if ok else "canceled", sid))
            except Exception:
                execute("UPDATE schedules SET status='canceled' WHERE id=?", (sid,))

    sched.add_job(tick, "interval", seconds=10, id="publisher_tick", replace_existing=True)
    sched.start()
    return sched

async def publish_now(bot: Bot, draft_id: int) -> bool:
    """Быстрая публикация — не трогаем слоты."""
    return await _publish(bot, draft_id, get_channel_id())

# ------------ helpers ------------
def _escape_html(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _render_html(body: str) -> str:
    safe = _escape_html(body or "")
    safe = safe.replace(TRAILING_URL, f'<a href="{TRAILING_URL}">{TRAILING_TEXT}</a>')
    if f'href="{TRAILING_URL}"' not in safe:
        if safe.strip():
            safe += "\n\n"
        safe += f'<a href="{TRAILING_URL}">{TRAILING_TEXT}</a>'
    return safe

def _build_keyboard(buttons_json: str | None) -> InlineKeyboardMarkup | None:
    if not buttons_json:
        return None
    try:
        import json
        items = json.loads(buttons_json) or []
        if not items:
            return None
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        b = InlineKeyboardBuilder()
        row_buf = []
        for i, it in enumerate(items, 1):
            row_buf.append(InlineKeyboardButton(text=it["text"], url=it["url"]))
            if i % 2 == 0:
                b.row(*row_buf); row_buf = []
        if row_buf:
            b.row(*row_buf)
        return b.as_markup()
    except Exception:
        return None

# ------------ publish ------------
async def _publish(bot: Bot, draft_id: int, channel_id: int | None):
    import json
    row = fetchone(
        "SELECT content_type, text, parse_mode, disable_web_page_preview, silent, "
        "media_file_id, album_json, buttons_json "
        "FROM drafts WHERE id=?",
        (draft_id,)
    )
    if not row:
        return False

    content_type, text, _parse_mode, disable_preview, silent, media_file_id, album_json, buttons_json = row
    chat_id = channel_id
    kb = _build_keyboard(buttons_json)
    html = _render_html(text or "")

    # Текст
    if content_type == "text":
        await bot.send_message(
            chat_id, html[:4096],
            disable_web_page_preview=True,
            disable_notification=bool(silent),
            reply_markup=kb,
            parse_mode="HTML",
        )

    # Одиночное медиа
    elif content_type in ("photo", "video", "document"):
        cap = html if len(html) <= 1024 else None
        if content_type == "photo":
            await bot.send_photo(chat_id, media_file_id, caption=cap,
                                 disable_notification=bool(silent), reply_markup=kb if cap else None,
                                 parse_mode="HTML" if cap else None)
        elif content_type == "video":
            await bot.send_video(chat_id, media_file_id, caption=cap,
                                 disable_notification=bool(silent), reply_markup=kb if cap else None,
                                 parse_mode="HTML" if cap else None)
        else:
            await bot.send_document(chat_id, media_file_id, caption=cap,
                                    disable_notification=bool(silent), reply_markup=kb if cap else None,
                                    parse_mode="HTML" if cap else None)
        if not cap:
            # остаток текстом (лимит Telegram)
            await bot.send_message(
                chat_id, html[:4096],
                disable_web_page_preview=True,
                disable_notification=bool(silent),
                reply_markup=kb,
                parse_mode="HTML",
            )

    # Альбом
    elif content_type == "album":
        try:
            items = json.loads(album_json or "[]")
        except Exception:
            items = []
        if not items:
            await bot.send_message(chat_id, "(пустой альбом)", disable_notification=bool(silent), reply_markup=kb)
        else:
            use_caption = html and len(html) <= 1024
            media = []
            for i, it in enumerate(items):
                cap = html if (i == 0 and use_caption) else None
                t, fid = it["type"], it["file_id"]
                if t == "photo":
                    media.append(InputMediaPhoto(media=fid, caption=cap, parse_mode="HTML" if cap else None))
                elif t == "video":
                    media.append(InputMediaVideo(media=fid, caption=cap, parse_mode="HTML" if cap else None))
                else:
                    media.append(InputMediaDocument(media=fid, caption=cap, parse_mode="HTML" if cap else None))
            await bot.send_media_group(chat_id, media=media, disable_notification=bool(silent))
            if not use_caption or kb:
                await bot.send_message(
                    chat_id, html[:4096],
                    disable_web_page_preview=True,
                    disable_notification=bool(silent),
                    reply_markup=kb,
                    parse_mode="HTML",
                )
    else:
        return False

    execute("UPDATE drafts SET status='published', published_at=CURRENT_TIMESTAMP WHERE id=?", (draft_id,))
    return True
