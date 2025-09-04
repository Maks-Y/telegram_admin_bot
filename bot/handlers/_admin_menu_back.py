
# Hotfix: обработчик "⬅️ В меню" из разделов админки
from aiogram import F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def _kb_root_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📰 RSS‑каналы", callback_data="admin:rss"),
         InlineKeyboardButton(text="⚙️ Настройки",  callback_data="admin:settings")],
        [InlineKeyboardButton(text="🗓 Очередь", callback_data="menu:queue"),
         InlineKeyboardButton(text="📄 Черновики", callback_data="menu:drafts")],
        [InlineKeyboardButton(text="🗂 Архив", callback_data="menu:archive"),
         InlineKeyboardButton(text="❓ Справка", callback_data="admin:help")]
    ])

@router.callback_query(F.data == "admin:menu")
async def cb_admin_menu(cb):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    await cb.message.edit_text("Выберите раздел:", reply_markup=_kb_root_menu())
    await cb.answer()
