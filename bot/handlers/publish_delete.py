from aiogram import Router, F
from aiogram.types import CallbackQuery
from ..config import get_config
from ..db import execute
from ..scheduler import publish_now

router = Router()
cfg = get_config()

def _is_admin(uid: int) -> bool:
    return (not cfg.admin_ids) or (uid in cfg.admin_ids)

@router.callback_query(F.data.startswith("pub:"))
async def publish(cb: CallbackQuery):
    """
    Быстрая публикация конкретного черновика.
    Не трогаем уже запланированные слоты.
    """
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return

    did = int(cb.data.split(":")[1])
    try:
        ok = await publish_now(cb.message.bot, did)
        await cb.message.answer("✅ Опубликовано." if ok else "Не удалось опубликовать.")
        await cb.answer()
    except Exception as e:
        await cb.message.answer(f"Ошибка публикации: <code>{e}</code>", parse_mode="HTML")
        await cb.answer()

@router.callback_query(F.data.startswith("del:"))
async def delete_draft(cb: CallbackQuery):
    """
    Удаляем черновик и отменяем его будущие слоты.
    """
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return

    did = int(cb.data.split(":")[1])
    execute("UPDATE drafts SET status='deleted' WHERE id=?", (did,))
    execute("UPDATE schedules SET status='canceled' WHERE draft_id=? AND status IN ('pending','running')", (did,))
    await cb.message.answer(f"Черновик №{did} удалён и слоты отменены.")
    await cb.answer()
