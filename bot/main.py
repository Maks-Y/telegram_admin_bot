import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from .config import get_config
from .db import init_db
from .scheduler import setup_scheduler
from .rss_worker import setup_rss_worker
from .handlers import (
    start,
    drafts_archive,
    admin_panel,
    menu,
    channel_bind,
    forwarded_to_draft,
    edit_text,
    edit_media,
    edit_buttons,
    schedule,
    publish_delete,
    queue,  # список/карточки запланированных: /queue, кнопки
    _admin_menu_back,
)


async def main():
    # Логирование
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    cfg = get_config()
    if not cfg.bot_token:
        raise SystemExit("BOT_TOKEN не задан в .env")

    # Создаём БД/таблицы при первом запуске
    init_db()

    # aiogram 3.7+: parse_mode через DefaultBotProperties
    bot = Bot(
        token=cfg.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # На всякий случай убираем webhook, чтобы не было конфликта с long polling
    await bot.delete_webhook(drop_pending_updates=True)

    # Регистрируем роутеры
    dp = Dispatcher()
    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(channel_bind.router)
    dp.include_router(forwarded_to_draft.router)
    dp.include_router(edit_text.router)
    dp.include_router(edit_media.router)
    dp.include_router(edit_buttons.router)
    dp.include_router(schedule.router)
    dp.include_router(publish_delete.router)
    dp.include_router(drafts_archive.router)
    dp.include_router(queue.router)  # /queue и управление слотами
    dp.include_router(admin_panel.router)
    dp.include_router(_admin_menu_back.router)

    # Планировщик публикаций по расписанию
    setup_scheduler(bot)

    # Стартуем RSS‑воркер (локальный ИИ на CPU)
    setup_rss_worker(bot)

    logging.info("Bot is running (long polling mode)...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
