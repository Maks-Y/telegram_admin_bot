import json
from aiogram import Router, F
from aiogram.types import Message, ContentType
from ..db import execute, fetchone
from ..keyboards import draft_controls
from ..config import get_config
from ..utils.media_group_buffer import MediaGroupBuffer

router = Router()
cfg = get_config()
buffer = MediaGroupBuffer()

def _is_admin(uid: int) -> bool:
    return (not cfg.admin_ids) or (uid in cfg.admin_ids)

# ------ helpers ------

def _escape_html(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _render_html(body: str) -> str:
    """Экранируем HTML и делаем красивую ссылку без превью."""
    safe = _escape_html(body or "")
    safe = safe.replace(TRAILING_URL, f'<a href="{TRAILING_URL}">{TRAILING_TEXT}</a>')
    if f'href="{TRAILING_URL}"' not in safe:
        if safe.strip():
            safe += "\n\n"
        safe += f'<a href="{TRAILING_URL}">{TRAILING_TEXT}</a>'
    return safe

def _caption_1024(html: str) -> str | None:
    """Вернуть подпись, если влезает в лимит 1024 символа."""
    if not html:
        return None
    return html if len(html) <= 1024 else None

# ------ preview ------
async def _show_preview(message: Message, draft_id: int):
    """
    Предпросмотр одним блоком:
      - одиночное медиа: медиа + подпись (если влезает), иначе медиа + остаток текстом;
      - альбом: первая медиа + подпись (если влезает), иначе альбомная карточка без подписи + текстом;
      - текст: просто текст.
    """
    row = fetchone(
        "SELECT content_type, text, media_file_id, album_json FROM drafts WHERE id=?",
        (draft_id,)
    )
    if not row:
        await message.answer("Черновик не найден.")
        return

    content_type, text, media_file_id, album_json = row
    html = _render_html(text or "")
    kb = draft_controls(draft_id)

    try:
        if content_type == "text":
            await message.answer(html[:4096], parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
            return

        if content_type in ("photo", "video", "document"):
            cap = _caption_1024(html)
            if content_type == "photo":
                await message.answer_photo(media_file_id, caption=cap, parse_mode="HTML" if cap else None,
                                           reply_markup=kb if cap else None)
            elif content_type == "video":
                await message.answer_video(media_file_id, caption=cap, parse_mode="HTML" if cap else None,
                                           reply_markup=kb if cap else None)
            else:
                await message.answer_document(media_file_id, caption=cap, parse_mode="HTML" if cap else None,
                                              reply_markup=kb if cap else None)
            if not cap:
                await message.answer(html[:4096], parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
            return

        if content_type == "album":
            items = []
            try:
                items = json.loads(album_json or "[]")
            except Exception:
                pass
            if not items:
                await message.answer("(пустой альбом)", reply_markup=kb)
                return

            first = items[0]
            cap = _caption_1024(html)
            if first["type"] == "photo":
                await message.answer_photo(first["file_id"], caption=cap, parse_mode="HTML" if cap else None,
                                           reply_markup=kb if cap else None)
            elif first["type"] == "video":
                await message.answer_video(first["file_id"], caption=cap, parse_mode="HTML" if cap else None,
                                           reply_markup=kb if cap else None)
            else:
                await message.answer_document(first["file_id"], caption=cap, parse_mode="HTML" if cap else None,
                                              reply_markup=kb if cap else None)
            if not cap:
                await message.answer(html[:4096], parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
            return

        await message.answer("Неподдерживаемый тип.")
    except Exception as e:
        await message.answer(f"(предпросмотр) Ошибка: <code>{e}</code>", parse_mode="HTML")

# ------ create draft from forwarded ------
@router.message(F.forward_origin | F.forward_from_chat | F.forward_sender_name)
async def on_forwarded(message: Message):
    if not _is_admin(message.from_user.id):
        return

    # Альбом
    if message.media_group_id:
        pack = await buffer.add_and_collect(message.media_group_id, message)
        if not pack:
            return

        items, caption = [], None
        for m in pack:
            if m.content_type == ContentType.PHOTO:
                items.append({"type": "photo", "file_id": m.photo[-1].file_id})
                caption = caption or m.caption
            elif m.content_type == ContentType.VIDEO:
                items.append({"type": "video", "file_id": m.video.file_id})
                caption = caption or m.caption
            elif m.content_type == ContentType.DOCUMENT:
                items.append({"type": "document", "file_id": m.document.file_id})
                caption = caption or m.caption

        if not items:
            await message.answer("Этот тип альбома пока не поддержан.")
            return

        cur = execute(
            "INSERT INTO drafts(author_id, content_type, text, album_json, parse_mode, status) "
            "VALUES (?,?,?,?, 'HTML','draft')",
            (message.from_user.id, "album", caption, json.dumps(items, ensure_ascii=False))
        )
        did = cur.lastrowid
        await message.answer(f"Создан черновик (альбом) №{did}")
        await _show_preview(message, did)
        return

    # Одиночные типы
    ctype, text, file_id = None, None, None
    if message.content_type == ContentType.TEXT:
        ctype = "text"; text = message.text
    elif message.content_type == ContentType.PHOTO:
        ctype = "photo"; file_id = message.photo[-1].file_id; text = message.caption
    elif message.content_type == ContentType.VIDEO:
        ctype = "video"; file_id = message.video.file_id; text = message.caption
    elif message.content_type == ContentType.DOCUMENT:
        ctype = "document"; file_id = message.document.file_id; text = message.caption
    else:
        await message.answer("Пока поддержаны текст/фото/видео/документ/альбом.")
        return

    cur = execute(
        "INSERT INTO drafts(author_id, content_type, text, media_file_id, parse_mode, status) "
        "VALUES (?,?,?,?, 'HTML','draft')",
        (message.from_user.id, ctype, text, file_id)
    )
    did = cur.lastrowid
    await message.answer(f"Создан черновик №{did}")
    await _show_preview(message, did)
