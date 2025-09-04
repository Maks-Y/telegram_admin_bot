from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from ..config import get_config
from ..db import get_setting
from ..keyboards import draft_controls

router = Router()
cfg = get_config()

def _is_admin(user_id: int) -> bool:
    return (not cfg.admin_ids) or (user_id in cfg.admin_ids)

@router.message(CommandStart())
async def start(message: Message):
    if not _is_admin(message.from_user.id):
        await message.answer("Доступ запрещён.")
        return
    ch = get_setting("TARGET_CHANNEL_ID") or (cfg.target_channel_id and str(cfg.target_channel_id)) or "—"
    await message.answer(
        "Готов к работе ✅\n"
        f"Канал публикации: <code>{ch}</code>\n"
        "Перешлите пост конкурента — создам черновик.\n"
        "Настроить канал: /set_channel"
    )
