
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from ..db import fetchall
from ..config import get_config
from .forwarded_to_draft import _show_preview

router = Router(name="drafts_list")
cfg = get_config()

def _is_admin(uid: int) -> bool:
    return (not cfg.admin_ids) or (uid in cfg.admin_ids)

def _kb_from_rows(rows, prefix: str, page: int, per_page: int, back_cb: str = None) -> InlineKeyboardMarkup:
    kb = []
    for did, created_at, text in rows:
        date = (created_at or "")[:16].replace("T"," ")
        snippet = (text or "").strip().replace("\n", " ")
        if len(snippet) > 40: snippet = snippet[:40] + "…"
        kb.append([InlineKeyboardButton(text=f"{date} · {snippet}", callback_data=f"{prefix}:{did}")])
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="« Назад", callback_data=f"{prefix}:page:{page-1}"))
    if len(rows) == per_page:
        nav.append(InlineKeyboardButton(text="Вперёд »", callback_data=f"{prefix}:page:{page+1}"))
    if nav: kb.append(nav)
    if back_cb:
        kb.append([InlineKeyboardButton(text="⬅️ В меню", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=kb or [[InlineKeyboardButton(text="Нет элементов", callback_data="noop")]])

async def _show_drafts_list(message: Message, page: int = 1, per_page: int = 10):
    offset = (page-1)*per_page
    rows = fetchall("""
        SELECT id, created_at, text
        FROM drafts
        WHERE status IN ('draft','queued')
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    await message.answer("Черновики:", reply_markup=_kb_from_rows(rows, "dr", page, per_page, "admin:menu"))

async def _show_archive_list(message: Message, page: int = 1, per_page: int = 10):
    offset = (page-1)*per_page
    rows = fetchall("""
        SELECT id, COALESCE(published_at, created_at), text
        FROM drafts
        WHERE status IN ('published','deleted')
        ORDER BY COALESCE(published_at, created_at) DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    await message.answer("Архив:", reply_markup=_kb_from_rows(rows, "ar", page, per_page, "admin:menu"))

@router.callback_query(F.data == "menu:drafts")
async def cb_open_drafts(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    await _show_drafts_list(cb.message)
    await cb.answer()

@router.callback_query(F.data.startswith("dr:page:"))
async def cb_drafts_page(cb: CallbackQuery):
    page = int(cb.data.split(":")[2])
    await _show_drafts_list(cb.message, page=page)
    await cb.answer()

@router.callback_query(F.data.startswith("dr:"))
async def cb_draft_open(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    did = int(cb.data.split(":")[1])
    await _show_preview(cb.message, did)
    await cb.answer()

@router.callback_query(F.data == "menu:archive")
async def cb_open_archive(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    await _show_archive_list(cb.message)
    await cb.answer()

@router.callback_query(F.data.startswith("ar:page:"))
async def cb_archive_page(cb: CallbackQuery):
    page = int(cb.data.split(":")[2])
    await _show_archive_list(cb.message, page=page)
    await cb.answer()

@router.callback_query(F.data.startswith("ar:"))
async def cb_archive_open(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    did = int(cb.data.split(":")[1])
    await _show_preview(cb.message, did)
    await cb.answer()
