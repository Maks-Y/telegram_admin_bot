import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    bot_token: str
    admin_ids: set[int]
    target_channel_id: int | None
    data_dir: str
    default_parse_mode: str
    default_silent: bool
    default_disable_preview: bool
    timezone: str

def _parse_bool(val: str | None, default: bool) -> bool:
    if val is None: return default
    return val.lower() in {"1","true","yes","on"}

def get_config() -> Config:
    admins = {int(x) for x in os.getenv("ADMIN_IDS","").replace(" ","").split(",") if x}
    ch_raw = os.getenv("TARGET_CHANNEL_ID","").strip()
    return Config(
        bot_token=os.getenv("BOT_TOKEN",""),
        admin_ids=admins,
        target_channel_id=int(ch_raw) if ch_raw else None,
        data_dir=os.getenv("DATA_DIR","/app/data"),
        default_parse_mode=os.getenv("DEFAULT_PARSE_MODE","HTML"),
        default_silent=_parse_bool(os.getenv("DEFAULT_SILENT"), False),
        default_disable_preview=_parse_bool(os.getenv("DEFAULT_DISABLE_WEB_PAGE_PREVIEW"), True),
        timezone=os.getenv("TZ","Europe/Moscow"),
    )
