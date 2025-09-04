from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def draft_controls(draft_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"pub:{draft_id}"))
    kb.row(InlineKeyboardButton(text="🗓 Очередь",   callback_data=f"sched:{draft_id}"))
    kb.row(InlineKeyboardButton(text="✏️ Текст",        callback_data=f"edit_text:{draft_id}"),
           InlineKeyboardButton(text="🖼 Медиа",        callback_data=f"edit_media:{draft_id}"))
    kb.row(InlineKeyboardButton(text="🔗 Кнопки",       callback_data=f"edit_buttons:{draft_id}"))
    kb.row(InlineKeyboardButton(text="🗑 Удалить",      callback_data=f"del:{draft_id}"))
    return kb.as_markup()
