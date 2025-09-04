import json
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from ..db import execute
from ..config import get_config
from .forwarded_to_draft import _show_preview

router = Router()
cfg = get_config()

def _is_admin(uid: int) -> bool:
    return (not cfg.admin_ids) or (uid in cfg.admin_ids)

class BtnStates(StatesGroup):
    waiting = State()

@router.callback_query(F.data.startswith("edit_buttons:"))
async def ask_buttons(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    did = int(cb.data.split(":")[1])
    await state.update_data(draft_id=did)
    await state.set_state(BtnStates.waiting)
    await cb.message.answer(
        "Пришлите кнопки в формате (по одной на строку):\n"
        "<code>Текст 1 | https://example.com</code>\n"
        "<code>Текст 2 | https://example.org</code>\n"
        "Пустое сообщение — очистит кнопки."
    )
    await cb.answer()

@router.message(BtnStates.waiting)
async def set_buttons(message: Message, state: FSMContext):
    data = await state.get_data()
    did = data.get("draft_id")
    txt = (message.text or "").strip()
    if not txt:
        execute("UPDATE drafts SET buttons_json=NULL WHERE id=?", (did,))
        await message.answer("Кнопки очищены. Предпросмотр ниже:")
        await _show_preview(message, did)
        await state.clear(); return

    items = []
    for line in txt.splitlines():
        if "|" in line:
            t, u = line.split("|", 1)
            t = t.strip(); u = u.strip()
            if t and u:
                items.append({"text": t, "url": u})
    execute("UPDATE drafts SET buttons_json=? WHERE id=?", (json.dumps(items, ensure_ascii=False), did))
    await message.answer("Кнопки обновлены. Предпросмотр ниже:")
    await _show_preview(message, did)
    await state.clear()
