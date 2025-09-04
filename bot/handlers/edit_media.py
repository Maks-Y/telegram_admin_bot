from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, ContentType
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from ..db import execute, fetchone
from ..config import get_config
from ..keyboards import draft_controls
from ..handlers.forwarded_to_draft import _render_html  # используем тот же форматтер ссылок

router = Router()
cfg = get_config()

def _is_admin(uid: int) -> bool:
    return (not cfg.admin_ids) or (uid in cfg.admin_ids)

class MediaStates(StatesGroup):
    waiting = State()

@router.callback_query(F.data.startswith("edit_media:"))
async def ask_media(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return

    did = int(cb.data.split(":")[1])
    await state.update_data(draft_id=did)
    await state.set_state(MediaStates.waiting)
    await cb.message.answer("🖼 Пришлите новое медиа (фото/видео/документ). Альбомы пока не принимаются здесь.")
    await cb.answer()

@router.message(
    MediaStates.waiting,
    F.content_type.in_({ContentType.PHOTO, ContentType.VIDEO, ContentType.DOCUMENT})
)
async def set_media(message: Message, state: FSMContext):
    data = await state.get_data()
    did = int(data.get("draft_id"))

    # Определяем тип и file_id
    if message.content_type == ContentType.PHOTO:
        new_type, file_id = "photo", message.photo[-1].file_id
    elif message.content_type == ContentType.VIDEO:
        new_type, file_id = "video", message.video.file_id
    else:
        new_type, file_id = "document", message.document.file_id

    # Обновляем черновик (сбрасываем album_json, если было)
    execute(
        "UPDATE drafts SET content_type=?, media_file_id=?, album_json=NULL WHERE id=?",
        (new_type, file_id, did),
    )

    # Достаём актуальный текст черновика и собираем caption
    row = fetchone("SELECT text FROM drafts WHERE id=?", (did,))
    text = row[0] if row else ""
    html = _render_html(text or "")
    caption = html if html and len(html) <= 1024 else None

    kb = draft_controls(did)

    await message.answer("✅ Медиа обновлено. Предпросмотр ниже:")

    # Показываем предпросмотр: медиа + подпись (если влезает)
    if new_type == "photo":
        await message.answer_photo(file_id, caption=caption, parse_mode="HTML" if caption else None,
                                   reply_markup=kb if caption else None)
    elif new_type == "video":
        await message.answer_video(file_id, caption=caption, parse_mode="HTML" if caption else None,
                                   reply_markup=kb if caption else None)
    else:
        await message.answer_document(file_id, caption=caption, parse_mode="HTML" if caption else None,
                                      reply_markup=kb if caption else None)

    # Если подпись длинная — отправим текст отдельным сообщением с кнопками
    if not caption and html:
        await message.answer(
            html[:4096],
            parse_mode="HTML",
            reply_markup=kb,
            disable_web_page_preview=True
        )

    await state.clear()

@router.message(MediaStates.waiting)
async def reject_non_media(message: Message):
    await message.answer("Нужно отправить фото, видео или документ. Попробуйте ещё раз.")
