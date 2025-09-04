from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ChatType
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from ..db import set_setting
from ..config import get_config

router = Router()
cfg = get_config()

def _is_admin(uid: int) -> bool:
    return (not cfg.admin_ids) or (uid in cfg.admin_ids)

class BindStates(StatesGroup):
    waiting_channel_forward = State()

@router.message(Command("set_channel"))
async def ask_channel(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        await message.answer("Доступ запрещён.")
        return
    await message.answer("Перешлите сюда <b>любой пост из нужного канала</b> (форвардом).")
    await state.set_state(BindStates.waiting_channel_forward)

@router.message(BindStates.waiting_channel_forward)
async def handle_forward(message: Message, state: FSMContext):
    fwd = message.forward_from_chat
    if fwd and fwd.type == ChatType.CHANNEL:
        set_setting("TARGET_CHANNEL_ID", str(fwd.id))
        await message.answer(f"Канал сохранён: <code>{fwd.id}</code>")
        await state.clear()
    else:
        await message.answer("Это не похоже на пересланный пост из канала. Попробуйте ещё раз.")
