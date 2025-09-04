from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from ..db import execute, fetchone
from ..config import get_config
from ..keyboards import draft_controls
from ..handlers.forwarded_to_draft import _render_html

router = Router()
cfg = get_config()

def _is_admin(uid: int) -> bool:
    return (not cfg.admin_ids) or (uid in cfg.admin_ids)

class TextStates(StatesGroup):
    waiting = State()

@router.callback_query(F.data.startswith("edit_text:"))
async def ask_text(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    did = int(cb.data.split(":")[1])
    await state.update_data(draft_id=did)
    await state.set_state(TextStates.waiting)
    await cb.message.answer("✏️ Отправьте новый текст/подпись (HTML допустим).")
    await cb.answer()

@router.message(TextStates.waiting)
async def set_text(message: Message, state: FSMContext):
    data = await state.get_data()
    did = data.get("draft_id")
    new_text = message.text or message.html_text or ""

    # Обновляем в БД
    execute("UPDATE drafts SET text=? WHERE id=?", (new_text, did))

    # Достаём обновлённый текст
    row = fetchone("SELECT text FROM drafts WHERE id=?", (did,))
    updated_text = row[0] if row else ""
    html = _render_html(updated_text)

    kb = draft_controls(did)

    # Показываем предпросмотр с новым текстом
    await message.answer("✅ Текст обновлён. Предпросмотр ниже:")
    await message.answer(
        html[:4096],
        parse_mode="HTML",
        reply_markup=kb,
        disable_web_page_preview=True
    )

    await state.clear()
