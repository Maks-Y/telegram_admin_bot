
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from ..config import get_config
from ..db import execute, fetchall, fetchone, get_setting, set_setting

router = Router(name="admin_panel")
cfg = get_config()

def ensure_schema():
    execute("""
    CREATE TABLE IF NOT EXISTS feeds(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE NOT NULL,
        title TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        etag TEXT,
        last_modified TEXT,
        tags TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
ensure_schema()

def _is_admin(uid: int) -> bool:
    return (not cfg.admin_ids) or (uid in cfg.admin_ids)

def _kb_admin_menu() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📰 RSS‑каналы", callback_data="admin:rss")],
        [InlineKeyboardButton(text="⚙️ Настройки",  callback_data="admin:settings")],
        [InlineKeyboardButton(text="🗓 Очередь",    callback_data="admin:queue")],
        [InlineKeyboardButton(text="❓ Справка",    callback_data="admin:help")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.message(Command("admin"))
async def admin_home(message: Message):
    if not _is_admin(message.from_user.id):
        await message.answer("Доступ запрещён.")
        return
    ch = get_setting("TARGET_CHANNEL_ID") or (cfg.target_channel_id and str(cfg.target_channel_id)) or "—"
    await message.answer("🛠 Панель администратора\n" f"Канал: <code>{ch}</code>", reply_markup=_kb_admin_menu())

@router.callback_query(F.data == "admin:rss")
async def cb_rss_home(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    await cb.message.edit_text("📰 RSS‑каналы", reply_markup=_kb_rss_list())
    await cb.answer()

class RssStates(StatesGroup):
    waiting_url = State()
    waiting_title = State()

def _kb_rss_list() -> InlineKeyboardMarkup:
    rows = []
    feeds = fetchall("SELECT id, url, COALESCE(title,''), COALESCE(active,1) FROM feeds ORDER BY id DESC", ())
    for fid, url, title, active in feeds:
        st = "🔔" if active else "🔕"
        rows.append([InlineKeyboardButton(text=f"{st} {title or url}", callback_data=f"rss:toggle:{fid}")])
        rows.append([InlineKeyboardButton(text="✏️ Название", callback_data=f"rss:retitle:{fid}"),
                     InlineKeyboardButton(text="🗑 Удалить",   callback_data=f"rss:del:{fid}")])
    rows.append([InlineKeyboardButton(text="➕ Добавить", callback_data="rss:add")])
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.callback_query(F.data == "rss:add")
async def cb_rss_add(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    await state.set_state(RssStates.waiting_url)
    await cb.message.answer("Вставьте URL RSS‑ленты (http/https):")
    await cb.answer()

@router.message(RssStates.waiting_url)
async def rss_receive_url(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        await message.answer("Доступ запрещён."); return
    url = (message.text or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await message.answer("Некорректный URL. Пришлите ссылку целиком (http/https)."); return
    await state.update_data(url=url)
    await state.set_state(RssStates.waiting_title)
    await message.answer("Ок. Введите короткое название (или «—»).")

@router.message(RssStates.waiting_title)
async def rss_receive_title(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        await message.answer("Доступ запрещён."); return
    title = (message.text or "").strip()
    if title == "—": title = ""
    data = await state.get_data(); url = data.get("url")
    execute("INSERT OR IGNORE INTO feeds(url, title, active) VALUES(?,?,1)", (url, title))
    await state.clear()
    await message.answer("✅ Лента добавлена.")

@router.callback_query(F.data.startswith("rss:toggle:"))
async def cb_rss_toggle(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    fid = int(cb.data.split(":")[2])
    row = fetchone("SELECT active FROM feeds WHERE id=?", (fid,))
    newv = 0 if int(row[0]) else 1
    execute("UPDATE feeds SET active=? WHERE id=?", (newv, fid))
    await cb.message.edit_text("📰 RSS‑каналы", reply_markup=_kb_rss_list())
    await cb.answer()

@router.callback_query(F.data.startswith("rss:retitle:"))
async def cb_rss_retitle(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    fid = int(cb.data.split(":")[2])
    await state.update_data(fid=fid)
    await state.set_state(RssStates.waiting_title)
    await cb.message.answer("Введите новое название (или «—»).")
    await cb.answer()

@router.callback_query(F.data.startswith("rss:del:"))
async def cb_rss_del(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    fid = int(cb.data.split(":")[2])
    execute("DELETE FROM feeds WHERE id=?", (fid,))
    await cb.message.edit_text("📰 RSS‑каналы", reply_markup=_kb_rss_list())
    await cb.answer()

# Settings
class SettingsStates(StatesGroup):
    waiting_value = State()

def _kb_settings() -> InlineKeyboardMarkup:
    rows = []
    for key, title in [("TARGET_CHANNEL_ID","ID канала"),("TRAILING_URL","Ссылка‑хвост"),("TRAILING_TEXT","Текст хвоста"),("TZ","Часовой пояс"),("RSS_POLL_INTERVAL","Интервал RSS, сек")]:
        val = get_setting(key)
        rows.append([InlineKeyboardButton(text=f"{title}: {val or '—'}", callback_data=f"set:key:{key}")])
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.callback_query(F.data == "admin:settings")
async def cb_settings_home(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    await cb.message.edit_text("⚙️ Настройки", reply_markup=_kb_settings()); await cb.answer()

@router.callback_query(F.data.startswith("set:key:"))
async def cb_settings_key(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True); return
    key = cb.data.split(":")[2]
    await state.set_state(SettingsStates.waiting_value); await state.update_data(key=key)
    await cb.message.answer(f"Введите значение для «{key}». Чтобы очистить — «—»."); await cb.answer()

@router.message(SettingsStates.waiting_value)
async def settings_receive_value(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        await message.answer("Нет доступа."); return
    data = await state.get_data(); key = data.get("key"); val = (message.text or "").strip()
    if val == "—":
        execute("DELETE FROM settings WHERE key=?", (key,)); await state.clear()
        await message.answer("✅ Сброшено."); return
    if key == "TARGET_CHANNEL_ID":
        try: int(val)
        except ValueError: await message.answer("Нужно целое число."); return
    set_setting(key, val); await state.clear(); await message.answer("✅ Сохранено.")


@router.callback_query(F.data == "admin:help")
async def cb_admin_help(cb: CallbackQuery):
    await cb.message.answer("Справка: используйте меню для управления лентами, настройками, очередью, черновиками и архивом.")
    await cb.answer()
