
import asyncio
import logging
import os
import re
import hashlib
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import httpx
from aiogram import Bot
from email.utils import parsedate_to_datetime

from .db import fetchall, fetchone, execute, init_db

log = logging.getLogger(__name__)

__all__ = [
    "process_feeds_once",
    "setup_scheduler",
    "setup_rss_worker",
]

# ------------------------
# Настройки
# ------------------------
DEFAULT_INTERVAL_SEC = int(os.getenv("RSS_POLL_INTERVAL", "180"))
MAX_ITEMS_PER_CYCLE = int(os.getenv("RSS_MAX_PER_CYCLE", "10"))  # <= 10 по требованию
NOTIFY_PER_CYCLE = int(os.getenv("RSS_NOTIFY_PER_CYCLE", "3"))

RSS_INCLUDE_LINK = os.getenv("RSS_INCLUDE_LINK", "1").lower() not in {
    "0", "false", "no", "off"
}

TZ_NAME = os.getenv("TZ", "UTC")

def _local_now() -> datetime:
    # Используем системную таймзону контейнера (TZ устанавливается через env)
    return datetime.now().astimezone()

def _start_of_today_local() -> datetime:
    now = _local_now()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)

# Срез по «только сегодня» на момент запуска процесса
RSS_CUTOFF_ISO = _start_of_today_local().isoformat()

# ------------------------
# Вспомогательные функции
# ------------------------
def _parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone()
    except Exception:
        return None

def _text_clean(s: str) -> str:
    if not s:
        return ""
    # Уберем html-теги и лишние пробелы
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s, flags=re.M).strip()
    return s

def _hash_item(parts: List[str]) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update((p or "").encode("utf-8", errors="ignore"))
        h.update(b"\x1f")
    return h.hexdigest()

async def _http_get(client: httpx.AsyncClient, url: str) -> Optional[str]:
    try:
        r = await client.get(url, timeout=15)
        r.raise_for_status()
        return r.text
    except Exception as e:
        log.warning("HTTP GET failed %s: %s", url, e)
        return None

def _xml_findall(text: str, tag: str) -> List[str]:
    # очень простой извлекатель <tag>...</tag> из RSS (чтобы не тянуть лишние зависимости)
    # не идеален, но для большинства лент работает
    pat = re.compile(rf"<{tag}[^>]*>(.*?)</{tag}>", re.I | re.S)
    return pat.findall(text or "")

def _xml_first(text: str, tag: str) -> Optional[str]:
    arr = _xml_findall(text, tag)
    return arr[0] if arr else None

def _extract_items(rss_xml: str) -> List[Dict[str, Any]]:
    # Ищем block <item>...</item>
    items_raw = re.findall(r"<item\b.*?</item>", rss_xml or "", re.I | re.S)
    items: List[Dict[str, Any]] = []
    for raw in items_raw:
        title = _xml_first(raw, "title") or ""
        link = _xml_first(raw, "link") or ""
        guid = _xml_first(raw, "guid") or ""
        pubdate = _xml_first(raw, "pubDate") or _xml_first(raw, "published") or _xml_first(raw, "updated")
        description = _xml_first(raw, "description") or ""
        items.append({
            "title": _text_clean(title),
            "link": link.strip(),
            "guid": guid.strip(),
            "pubdate": pubdate.strip() if pubdate else None,
            "summary": _text_clean(description),
            "raw": raw,
        })
    return items

def _already_seen(hash_hex: str) -> bool:
    row = fetchone("SELECT 1 FROM drafts WHERE hash = ? LIMIT 1", (hash_hex,))
    return bool(row)

def _insert_draft(text: str, media_url: Optional[str], source_url: str, hash_hex: str) -> int:
    content_type = "photo" if media_url else "text"
    cur = execute(
        "INSERT INTO drafts (author_id, content_type, text, media_url, source_url, hash, status, created_at) "
        "VALUES (0, ?, ?, ?, ?, ?, 'draft', datetime('now'))",
        (content_type, text, media_url, source_url, hash_hex),
    )
    return int(cur.lastrowid) if cur else 0

async def _notify_admins(bot: Bot, draft_id: int, title: str):
    # Пытаемся взять список админов из таблицы настроек, иначе из ENV ADMIN_IDS через запятую
    admin_ids: List[int] = []
    try:
        rows = fetchall("SELECT value FROM settings WHERE key='admin_ids' LIMIT 1")
        if rows and rows[0] and rows[0][0]:
            admin_ids = [int(x) for x in rows[0][0].replace(" ", "").split(",") if x]
    except Exception:
        pass
    if not admin_ids:
        env_ids = os.getenv("ADMIN_IDS", "")
        if env_ids:
            admin_ids = [int(x) for x in env_ids.replace(" ", "").split(",") if x]

    for uid in admin_ids[:3]:
        try:
            await bot.send_message(uid, f"🤖 Новый черновик #{draft_id}: {title[:120]}")
        except Exception as e:
            log.warning("notify_admin %s failed: %s", uid, e)

def _build_post_text(title: str, summary: str, url: str) -> str:
    title = _text_clean(title)
    summary = _text_clean(summary)
    blocks: List[str] = []
    if title:
        blocks.append(title)
    if summary:
        blocks.append(summary)
    if RSS_INCLUDE_LINK and url:
        blocks.append(url)
    return "\n\n".join([b for b in blocks if b])

async def _try_extract_og_image(client: httpx.AsyncClient, url: str) -> Optional[str]:
    html = await _http_get(client, url)
    if not html:
        return None
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    if m:
        return m.group(1)
    return None

# ------------------------
# Основной цикл
# ------------------------
async def process_feeds_once(bot: Bot):
    # только активные фиды
    feeds = fetchall("SELECT id, url FROM feeds WHERE COALESCE(active,1)=1 ORDER BY id DESC")
    if not feeds:
        log.info("RSS: нет активных каналов")
        return

    cutoff = datetime.fromisoformat(RSS_CUTOFF_ISO)
    log.info("RSS cutoff: %s", cutoff.isoformat())

    async with httpx.AsyncClient(follow_redirects=True, headers={"User-Agent":"bot/rss-worker"}) as client:
        for fid, url in feeds:
            rss = await _http_get(client, url)
            if not rss:
                continue
            items = _extract_items(rss)

            # Отсечение глубины: берём не более MAX_ITEMS_PER_CYCLE из верхушки ленты
            items = items[:MAX_ITEMS_PER_CYCLE]

            # Фильтруем по дате >= cutoff и по уникальности
            prepared: List[Dict[str, Any]] = []
            for it in items:
                pub = _parse_date(it.get("pubdate"))
                if pub and pub < cutoff:
                    continue  # старое
                title = it.get("title") or ""
                link = it.get("link") or ""
                guid = it.get("guid") or ""
                hash_hex = _hash_item([str(fid), guid, link, title])
                if _already_seen(hash_hex):
                    continue
                prepared.append({**it, "hash": hash_hex})

            if not prepared:
                continue

            # Ограничим кол-во «шумных» уведомлений
            notif_left = NOTIFY_PER_CYCLE

            for it in prepared:
                # малые уступки loop'у
                await asyncio.sleep(0)

                title = it["title"]
                link = it["link"] or it["guid"] or ""
                summary = it.get("summary") or ""

                # попытка вытащить обложку (без падений)
                media_url = None
                try:
                    media_url = await _try_extract_og_image(client, link) if link else None
                except Exception:
                    media_url = None

                text = _build_post_text(title, summary, link)
                draft_id = _insert_draft(text=text, media_url=media_url, source_url=link, hash_hex=it["hash"])
                log.info("RSS draft #%s created from feed %s", draft_id, fid)

                if notif_left > 0:
                    try:
                        await _notify_admins(bot, draft_id, title)
                    finally:
                        notif_left -= 1


# ------------------------
# Планировщик
# ------------------------
def setup_scheduler(scheduler, bot: Bot, interval_sec: Optional[int] = None):
    """Регистрирует периодическую задачу. Вызывать из main после старта dp/bot.

    Пример:
        scheduler = AsyncIOScheduler(timezone=TZ_NAME)
        setup_scheduler(scheduler, bot, interval_sec=120)
        scheduler.start()
    """
    from apscheduler.triggers.interval import IntervalTrigger

    sec = interval_sec or DEFAULT_INTERVAL_SEC
    sec = max(30, min(sec, 3600))  # безопасность
    log.info("Setup RSS scheduler: every %ss", sec)

    async def tick():
        try:
            await process_feeds_once(bot)
        except Exception as e:
            log.exception("RSS tick error: %s", e)

    scheduler.add_job(tick, trigger=IntervalTrigger(seconds=sec), id="rss_tick", replace_existing=True)


def setup_rss_worker(bot: Bot, interval_sec: int | None = None) -> AsyncIOScheduler:
    """Создаёт и запускает планировщик, выполняющий ``process_feeds_once``."""

    init_db()
    scheduler = AsyncIOScheduler(timezone=TZ_NAME)
    setup_scheduler(scheduler, bot, interval_sec)
    scheduler.start()
    return scheduler
