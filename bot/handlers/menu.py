
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from ..config import get_config
from ..db import get_setting
from .queue import _show_queue_list
from .drafts_archive import _show_drafts_list, _show_archive_list

router = Router(name="menu")

cfg = get_config()

def _is_admin(uid: int) -> bool:
    return (not cfg.admin_ids) or (uid in cfg.admin_ids)

def reply_compact_menu():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Меню")]],
        resize_keyboard=True
    )

def inline_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📰 RSS‑каналы", callback_data="admin:rss"),
         InlineKeyboardButton(text="⚙️ Настройки",  callback_data="admin:settings")],
        [InlineKeyboardButton(text="🗓 Очередь", callback_data="menu:queue"),
         InlineKeyboardButton(text="📄 Черновики", callback_data="menu:drafts")],
        [InlineKeyboardButton(text="🗂 Архив", callback_data="menu:archive"),
         InlineKeyboardButton(text="❓ Справка", callback_data="admin:help")]
    ])

@router.message(CommandStart())
async def on_start(message: Message):
    if not _is_admin(message.from_user.id):
        await message.answer("Доступ запрещён."); return
    ch = get_setting("TARGET_CHANNEL_ID") or (cfg.target_channel_id and str(cfg.target_channel_id)) or "—"
    await message.answer(
        "Готов к работе ✅\n"
        f"Канал публикации: <code>{ch}</code>\n"
        "Нажмите «Меню» ниже, чтобы открыть разделы.",
        reply_markup=reply_compact_menu()
    )

@router.message(Command("menu"))
async def cmd_menu(message: Message):
    if not _is_admin(message.from_user.id):
        return
    await message.answer("Выберите раздел:", reply_markup=inline_main_menu())

# Надёжный обработчик кнопки Reply «Меню» (без использования .lower() в фильтре)
@router.message(lambda m: isinstance(m.text, str) and m.text.strip().lower() in {"меню", "menu"})
async def text_menu(message: Message):
    if not _is_admin(message.from_user.id):
        return
    await message.answer("Выберите раздел:", reply_markup=inline_main_menu())

@router.callback_query(F.data == "menu:queue")
async def open_queue(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    await _show_queue_list(cb.message)
    await cb.answer()

# Переходы в черновики/архив (кнопки в главном меню)
@router.callback_query(F.data == "menu:drafts")
async def open_drafts(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    await _show_drafts_list(cb.message)
    await cb.answer()

@router.callback_query(F.data == "menu:archive")
async def open_archive(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    await _show_archive_list(cb.message)
    await cb.answer()
