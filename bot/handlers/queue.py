from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from ..db import fetchall, fetchone, execute
from ..config import get_config
from .forwarded_to_draft import _show_preview
from ..scheduler import publish_now

router = Router()
cfg = get_config()

def _is_admin(uid: int) -> bool:
    return (not cfg.admin_ids) or (uid in cfg.admin_ids)

# --------- helpers ----------
def _render_queue_kb():
    rows = fetchall(
        "SELECT s.id, s.draft_id, strftime('%d.%m %H:%M', s.run_at), d.content_type "
        "FROM schedules s JOIN drafts d ON d.id = s.draft_id "
        "WHERE s.status='pending' "
        "ORDER BY s.run_at ASC, s.id ASC LIMIT 50"
    )
    kb = InlineKeyboardBuilder()
    if not rows:
        kb.row(InlineKeyboardButton(text="(очередь пуста)", callback_data="qnoop"))
    else:
        for sid, did, run_at, ctype in rows:
            kb.row(InlineKeyboardButton(text=f"#{sid} • {run_at} • d{did} • {ctype}", callback_data=f"qs:{sid}"))
    return kb

async def _show_queue_list(msg: Message):
    kb = _render_queue_kb()
    text = "Запланированные публикации:"
    try:
        await msg.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await msg.answer(text, reply_markup=kb.as_markup())

# --------- commands ----------
@router.message(Command("queue"))
async def show_queue(message: Message):
    if not _is_admin(message.from_user.id):
        return
    await _show_queue_list(message)

# --------- callbacks ----------
@router.callback_query(F.data == "qback")
async def qback(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    await _show_queue_list(cb.message)
    await cb.answer()

@router.callback_query(F.data == "qrefresh")
async def qrefresh(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    await _show_queue_list(cb.message)
    await cb.answer("Обновлено")

@router.callback_query(F.data.startswith("qs:"))
async def open_slot(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    sid = int(cb.data.split(":")[1])
    row = fetchone(
        "SELECT s.id, s.draft_id, strftime('%d.%m.%Y %H:%M', s.run_at) "
        "FROM schedules s WHERE s.id=? AND s.status='pending'", (sid,)
    )
    if not row:
        await cb.message.answer("Слот не найден или уже неактивен.")
        await _show_queue_list(cb.message)
        await cb.answer(); return

    _, did, when = row
    await cb.message.answer(f"Слот #{sid} — запланирован на {when} (Мск).")
    await _show_preview(cb.message, did)

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Опубликовать сейчас", callback_data=f"qpub:{sid}"),
        InlineKeyboardButton(text="❌ Отменить слот", callback_data=f"qdel:{sid}")
    )
    kb.row(InlineKeyboardButton(text="🔙 К списку", callback_data="qback"))
    await cb.message.answer("Действия со слотом:", reply_markup=kb.as_markup())
    await cb.answer()

@router.callback_query(F.data.startswith("qdel:"))
async def qdel(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    sid = int(cb.data.split(":")[1])
    execute("UPDATE schedules SET status='canceled' WHERE id=? AND status!='done'", (sid,))
    await cb.message.answer(f"Слот #{sid} отменён.")
    await cb.answer()

@router.callback_query(F.data.startswith("qpub:"))
async def qpub(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    sid = int(cb.data.split(":")[1])
    row = fetchone("SELECT draft_id FROM schedules WHERE id=? AND status='pending'", (sid,))
    if not row:
        await cb.message.answer("Слот не найден или уже неактивен.")
        await cb.answer(); return
    did = int(row[0])
    ok = await publish_now(cb.message.bot, did)
    execute("UPDATE schedules SET status=? WHERE id=?", ("done" if ok else "canceled", sid))
    await cb.message.answer("✅ Опубликовано." if ok else "Не удалось опубликовать.")
    await cb.answer()
