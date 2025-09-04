from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from ..db import execute
from ..config import get_config
from ..utils.parse_dt import parse_user_dt
from .queue import _show_queue_list

router = Router()
cfg = get_config()

def _is_admin(uid: int) -> bool:
    return (not cfg.admin_ids) or (uid in cfg.admin_ids)

class SchedStates(StatesGroup):
    waiting = State()

@router.callback_query(F.data.startswith("sched:"))
async def ask_time(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    did = int(cb.data.split(":")[1])
    await state.update_data(draft_id=did)
    await state.set_state(SchedStates.waiting)
    await cb.message.answer(
        "Когда публикуем? (Мск)\n"
        "• <code>DD.MM.YYYY HH:MM</code>  —  02.09.2025 09:30\n"
        "• <code>YYYY-MM-DD HH:MM</code>\n"
        "• <code>HH:MM</code> — сегодня; если время прошло — завтра."
    )
    await cb.answer()

@router.message(SchedStates.waiting)
async def set_time(message: Message, state: FSMContext):
    try:
        dt = parse_user_dt(message.text, cfg.timezone or "Europe/Moscow")
    except Exception:
        await message.answer("Не распознал дату/время. Примеры: 02.09.2025 09:30, 2025-09-02 09:30, 09:30")
        return

    data = await state.get_data()
    did = int(data.get("draft_id"))
    execute("INSERT INTO schedules(draft_id, run_at) VALUES(?, ?)", (did, dt.strftime("%Y-%m-%d %H:%M:%S")))
    execute("UPDATE drafts SET status='queued' WHERE id=?", (did,))

    # Только подтверждение, без повторного поста
    await message.answer(f"Запланировано на {dt.strftime('%d.%m.%Y %H:%M')} (Мск). Команда: /queue — список.")
    await state.clear()
